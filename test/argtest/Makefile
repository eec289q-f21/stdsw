CC=clang 
CFLAGS=-Wall

all: args
program: args.o
program.o: args.c

clean:
	rm -f args args.o
run: program
	./args
