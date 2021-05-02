from conans import ConanFile, AutoToolsBuildEnvironment, VisualStudioBuildEnvironment, tools
from contextlib import contextmanager
import os

required_conan_version = ">=1.33.0"


class GetTextConan(ConanFile):
    name = "gettext"
    description = "An internationalization and localization system for multilingual programs"
    topics = ("conan", "gettext", "intl", "libintl", "i18n")
    url = "https://github.com/conan-io/conan-center-index"
    homepage = "https://www.gnu.org/software/gettext"
    license = "GPL-3.0-or-later"

    settings = "os", "arch", "compiler", "build_type"
    options = {
        "shared": [True, False],
        "fPIC": [True, False],
        "threads": [False, "posix", "solaris", "pth", "windows"],
    }
    default_options = {
        "shared": False,
        "fPIC": True,
        "threads": "posix",
    }

    exports_sources = ["patches/**"]
    _autotools = None

    @property
    def _source_subfolder(self):
        return "source_subfolder"

    @property
    def _is_msvc(self):
        return self.settings.compiler == "Visual Studio"

    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC
        # Default threads option
        if self.settings.os == "Windows":
            self.options.threads = "windows"
        elif self.settings.os == "SunOS":
            self.options.threads = "solaris"

    def configure(self):
        if self.options.shared:
            del self.options.fPIC
        del self.settings.compiler.libcxx
        del self.settings.compiler.cppstd

    def requirements(self):
        self.requires("libiconv/1.16")

    def build_requirements(self):
        self.build_requires("libtool/2.4.6")
        if tools.os_info.is_windows and not tools.get_env("CONAN_BASH_PATH"):
            self.build_requires("msys2/20200517")

    def source(self):
        tools.get(**self.conan_data["sources"][self.version],
                  destination=self._source_subfolder, strip_root=True)

    @contextmanager
    def _build_context(self):
        with tools.chdir(os.path.join(self._source_subfolder)):
            if self._is_msvc:
                with tools.vcvars(self.settings):
                    with tools.environment_append(VisualStudioBuildEnvironment(self).vars):
                        yield
            else:
                yield

    def _configure_autotools(self):
        if self._autotools:
            return self._autotools
        args = [
            "--{}-shared".format("enable" if self.options.shared else "disable"),
            "--{}-static".format("disable" if self.options.shared else "enable"),
            "HELP2MAN=/bin/true",
            "EMACS=no",
            "--disable-nls",
            "--disable-dependency-tracking",
            "--enable-relocatable",
            "--disable-c++",
            "--disable-java",
            "--disable-csharp",
            "--disable-libasprintf",
            "--disable-curses",
            "--enable-threads={}".format(self.options.threads) if bool(self.options.threads) else "--disable-threads",
            "--with-libiconv-prefix={}".format(tools.unix_path(self.deps_cpp_info["libiconv"].rootpath)),
        ]
        build = None
        host = None
        rc = None
        if self._is_msvc:
            # INSTALL.windows: Native binaries, built using the MS Visual C/C++ tool chain.
            build = False
            if self.settings.arch_build == "x86":
                host = "i686-w64-mingw32"
                rc = "windres --target=pe-i386"
            elif self.settings.arch_build == "x86_64":
                host = "x86_64-w64-mingw32"
                rc = "windres --target=pe-x86-64"
            args.extend([
                "CC={} cl -nologo".format(tools.unix_path(self.deps_user_info["automake"].compile)),
                "LD=link",
                "NM=dumpbin -symbols",
                "STRIP=:",
                "AR={} lib".format(tools.unix_path(self.deps_user_info["automake"].ar_lib)),
                "RANLIB=:",
            ])
            if rc:
                args.extend(["RC={}".format(rc), "WINDRES={}".format(rc)])
        self._autotools = AutoToolsBuildEnvironment(self, win_bash=tools.os_info.is_windows)
        if self._is_msvc:
            self._autotools.flags.append("-FS")
        self._autotools.configure(args=args, build=build, host=host)
        return self._autotools

    def build(self):
        for patch in self.conan_data.get("patches", {}).get(self.version, []):
            tools.patch(**patch)
        with self._build_context():
            self.run("{} -fiv".format(tools.get_env("AUTORECONF")), win_bash=tools.os_info.is_windows)
            autotools = self._configure_autotools()
            autotools.make()

    def package(self):
        self.copy(pattern="COPYING", dst="licenses", src=self._source_subfolder)
        with self._build_context():
            env_build = self._configure_autotools()
            env_build.install()
        self.copy(pattern="*.dll", dst="bin", src=self._source_subfolder, keep_path=False, symlinks=True)
        self.copy(pattern="*.lib", dst="lib", src=self._source_subfolder, keep_path=False, symlinks=True)
        self.copy(pattern="*.a", dst="lib", src=self._source_subfolder, keep_path=False, symlinks=True)
        self.copy(pattern="*.so*", dst="lib", src=self._source_subfolder, keep_path=False, symlinks=True)
        self.copy(pattern="*.dylib*", dst="lib", src=self._source_subfolder, keep_path=False, symlinks=True)
        self.copy(pattern="*libgnuintl.h", dst="include", src=self._source_subfolder, keep_path=False, symlinks=True)
        tools.rmdir(os.path.join(self.package_folder, "lib", "gettext"))
        tools.remove_files_by_mask(os.path.join(self.package_folder, "lib"), "*.la")
        os.rename(os.path.join(self.package_folder, "include", "libgnuintl.h"),
                  os.path.join(self.package_folder, "include", "libintl.h"))
        os.rename(os.path.join(self.package_folder, "share", "aclocal"),
                  os.path.join(self.package_folder, "bin", "aclocal"))
        tools.rmdir(os.path.join(self.package_folder, "share"))
        if self._is_msvc and self.options.shared:
            os.rename(os.path.join(self.package_folder, "lib", "gnuintl.dll.lib"),
                      os.path.join(self.package_folder, "lib", "gnuintl.lib"))

    def package_info(self):
        self.cpp_info.libs = ["gnuintl"]
        if self.settings.os == "Macos":
            self.cpp_info.frameworks.append("CoreFoundation")

        bindir = os.path.join(self.package_folder, "bin")
        self.output.info("Appending PATH environment variable: {}".format(bindir))
        self.env_info.PATH.append(bindir)

        gettext_aclocal = tools.unix_path(os.path.join(self.package_folder, "bin", "aclocal"))
        self.output.info("Appending AUTOMAKE_CONAN_INCLUDES environment variable: {}".format(gettext_aclocal))
        self.env_info.AUTOMAKE_CONAN_INCLUDES.append(gettext_aclocal)
