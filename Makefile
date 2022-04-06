SOURCES = $(wildcard *.py)
LINT = $(SOURCES:.py=.lint)
TEST = $(SOURCES:.py=.doctest)
ARG = test.ps3d
PYTHON ?= python3
PYLINT ?= pylint3  # may be simply `pylint`, especially on Debian 11+
export

all: lint test run
run: ps3d.py
	./$< $(ARG)
lint: $(LINT)
test: $(TEST)
%.lint: %.py
	$(PYLINT) $<
%.doctest: %.py
	$(PYTHON) -m doctest $<
