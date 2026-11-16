
#include <stdio.h>
#include <stdlib.h>
#include "channel.h"
#include "macros.h"

void usage(const char* exec_name)
{
    printf("%s in_path out_path - pull from channel in_path data, duplicate every character and push result into out_path channel\n", exec_name);
}

int main(int argc, char* argv[]) {
    if (argc != 3)
    {
        usage(argv[0]);
        exit(EXIT_FAILURE);
    }

    // Open channels here and start processing!
    // There is no more time left. What are you waiting for?

    return EXIT_SUCCESS;
}