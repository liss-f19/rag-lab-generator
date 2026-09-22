#define _POSIX_C_SOURCE 200809L

#include <errno.h>
#include <pthread.h>
#include <semaphore.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#ifndef TEMP_FAILURE_RETRY
#define TEMP_FAILURE_RETRY(expression)             \
    (__extension__({                               \
        long int __result;                         \
        do                                         \
            __result = (long int)(expression);     \
        while (__result == -1L && errno == EINTR); \
        __result;                                  \
    }))
#endif

#define ERR(source) (perror(source), fprintf(stderr, "%s:%d\n", __FILE__, __LINE__), exit(EXIT_FAILURE))

#define UNUSED(x) (void)(x)

void sleep_ms()
{
    struct timespec sleep_time = {0, 1000000L};
    TEMP_FAILURE_RETRY(nanosleep(&sleep_time, &sleep_time));
}

int read_int_cli()
{
    int number;
    int res = scanf("%d", &number);
    if (res == EOF)
        ERR("scanf");
    if (res == 0)
        number = 0;
    getchar();
    return number;
}

float read_float_cli()
{
    float number;
    int res = scanf("%f", &number);
    if (res == EOF)
        ERR("scanf");
    if (res == 0)
        number = 0;
    getchar();
    return number;
}

void hello_world_test(void *args)
{
    int* idx = (int*)args;

    printf("Hello world from worker %d!\n", *idx);
    free(args);

    sleep(5);
}
