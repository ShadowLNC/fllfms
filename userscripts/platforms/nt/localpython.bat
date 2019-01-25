:: This isn't the most glamourous, but we know that we're shipping Windows
:: builds with a built-in Python, so let's take advantage.

:: Filepaths may not be correct if we use pushd/popd.
@"%~dp0\lib\python.exe" %*
