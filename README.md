# conan-client-remote-s3

A bare-bones serverless Conan remote storing packages in S3 bucket.

This grew out of [this](https://github.com/conan-io/conan/issues/7115) discussion.

This package relies on [requests-adapter-injector](https://github.com/kshpytsya/requests-adapter-injector)
which does some global injection trickery, so it is recomended, if you do not do so already,
to install Conan in a dedicated venv. You may want to try [pipx](https://pypi.org/project/pipx/) tool
to manage venvs for Python-based tools.

If using `pipx`, you can install this as `pipx install conan && pipx inject conan conan-client-remote-s3`,
or just `pipx inject conan conan-client-remote-s3` if you already have Conan installed via `pipx`.

Otherwise, doing it manually:

```
$ python -mvenv venv
$ venv/bin/pip install conan conan-client-remote-s3
```

To add a remote do

```
$ conan remote add <remote-name> conan-s3://<s3-bucket-name>
```

Note that this remote does not support revisions, and most probably will not, as doing so would require
some distributed locking. [This](https://pypi.org/project/python-dynamodb-lock/) library implements
locking using AWS DynamoDB, however this would increase operational complexity.

Note: search functionality is yet to be implemented.
