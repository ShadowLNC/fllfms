:: We're shipping Windows builds with Python included, so let's take advantage.

:: Filepaths may not be correct if we use pushd/popd. Minimise interference by
:: disallowing user site packages (-s) and PYTHON* environment variables (-E).
@"%~dp0\lib\python.exe" -s -E %*
