# AbuseHelper [![Circle CI](https://circleci.com/gh/abusesa/abusehelper.svg?style=shield)](https://circleci.com/gh/abusesa/abusehelper)

AbuseHelper is an open-source framework for receiving and redistributing abuse feeds and threat intel.

## Running tests & linter

We run automated tests (for Python 2.6, 2.7 and PyPy) and flake8 linter for each repository push. View the logs at https://circleci.com/gh/abusesa/abusehelper.

To run the tests locally you need to have [```tox```](http://tox.testrun.org/) installed (for example via ```pip install tox```). Then, while in the project directory, run:

```
$ tox
```

## Changelog

See [CHANGELOG.md](./CHANGELOG.md).

## Security Announcements

 * [AbuseHelper Security Announcement 2016-01](./docs/SECURITY-2016-01.md).
   * Summary: Multiple places failed to check X.509 certificates leading to possibility to MITM connections.

## Community extensions

This project provides the core AbuseHelper functionality, including choice bots and tools.

The [AbuseHelper Community](https://bitbucket.org/ahcommunity/) repository builds upon the core, for example by offering a fine selection of community-maintained bots.

## License

Files are (c) respective copyright holders if named in the specific file, everything else is current (c) by Synopsys, Inc. Everything is licensed under [MIT license](http://www.opensource.org/licenses/mit-license.php), see [LICENSE](./LICENSE).
