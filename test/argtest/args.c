#include <stdio.h>

int main( int argc, char *argv[] )  {


   fprintf(stdout,"Program name %s\n", argv[0]);
 
   if( argc == 2 ) {
      fprintf(stdout,"The argument supplied is %s\n", argv[1]);
   }
   else if( argc > 2 ) {
      fprintf(stderr,"Too many arguments supplied.\n");
  }
   else {
      fprintf(stderr,"One argument expected.\n");
   }

   printf("Program terminated\n");
}
