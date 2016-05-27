CC      = g++
CFLAGS  = -O3 -std=c++0x -pg -D_DEBUG -g -c -Wall


all: main 

main: main.o fakefs.o
	$(CC) -o $@ $^

main.o: main.cpp fakefs.h
	$(CC) -c $(CFLAGS) $<

fakefs.o: fakefs.cpp fakefs.h
	$(CC) -c $(CFLAGS) $<

.PHONY: clean cleanest test

clean:
	rm main.o fakefs.o main

test: 
	./main
