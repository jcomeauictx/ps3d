SOURCES = $(wildcard *.py)
LINT = $(SOURCES:.py=.lint)
TEST = $(SOURCES:.py=.doctest)
PYTHON ?= python3
PYLINT ?= pylint3  # may be simply `pylint`, especially on Debian 11+
export

all: lint test run
run: test.view
lint: $(LINT)
test: $(TEST)
%.lint: %.py
	$(PYLINT) $<
%.doctest: %.py
	$(PYTHON) -m doctest $<
%.obj: ps3d.py %.ps3d
	./$+ $@
%.view: %.obj
	timeout 10 meshlab $<
view: a_test.view
%.ps: %.ps3d
	gs $<
ps: test.ps
.PRECIOUS: test.obj
