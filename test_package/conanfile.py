from conans import ConanFile, CMake, tools
import os
import shutil


class TestPackageConan(ConanFile):
    settings = "os", "arch", "compiler", "build_type"
    generators = "cmake"

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def test(self):
        if not tools.cross_building(self.settings):
            bin_path = os.path.join("bin", "test_package")
            for locale in ["en_US", "ru_RU", "es_ES"]:
                with tools.environment_append({"LANG": locale}):
                    self.run("%s %s" % (bin_path, os.path.abspath(self.source_folder)), run_environment=True)
