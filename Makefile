BASE_PATH := tmp
BASE_DIR := unx_ss
BASE_IDENT := server.s

test-server:
	nc -uU /${BASE_PATH}/${BASE_DIR}/${BASE_IDENT}

unittest:
	python3 -m unittest discover -p 'test_*.py'