README
--------

This branch has some magic memory bug likely related to python's `pyc`
compilation and I have no idea what it is.

Modify the enumeration name in 
(pyderive.tests.extensions.validate.ValidateTests.test_enum_value)[./pyderive/tests/extensions/validate.py]
and watch as the slots test in a completely different method/test-case/filename/folder will
fail randomly with the slots randomly missing.

Run the tests with:
```
python -m unittest pyderive.tests -v
```

This bug has been tested and confirmed from python 3.8.10 all the way to 3.11.3.
It likely effects up to the latest version.
