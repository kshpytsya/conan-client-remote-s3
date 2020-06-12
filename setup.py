import setuptools
import setuptools_scm.version


setuptools.setup(
    use_scm_version=dict(
        version_scheme=setuptools_scm.version.postrelease_version,
        local_scheme=lambda version: "",
    ),
)
