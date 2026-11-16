#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>

int main() {

    int err;

    pthread_mutexattr_t attr;
    if ((err = pthread_mutexattr_init(&attr)) != 0) {
        fprintf(stderr, "pthread_mutexattr_init(): %s", strerror(err));
        return 1;
    }

    // TODO: Try PTHREAD_MUTEX_ERRORCHECK, PTHREAD_MUTEX_RECURSIVE
    if ((err = pthread_mutexattr_settype(&attr, PTHREAD_MUTEX_DEFAULT)) != 0) {
        fprintf(stderr, "pthread_mutexattr_settype(): %s", strerror(err));
        return 1;
    }

    printf("Creating mutex...\n");
    pthread_mutex_t mtx;
    if ((err = pthread_mutex_init(&mtx, &attr)) != 0) {
        fprintf(stderr, "pthread_mutex_init(): %s", strerror(err));
        return 1;
    }

    printf("Locking mutex...\n");
    if ((err = pthread_mutex_lock(&mtx)) != 0) {
        fprintf(stderr, "pthread_mutex_lock(): %s", strerror(err));
        return 1;
    }

    printf("Locking mutex...\n");
    if ((err = pthread_mutex_lock(&mtx)) != 0) {
        fprintf(stderr, "pthread_mutex_lock(): %s", strerror(err));
        return 1;
    }

    printf("Unlocking mutex...\n");
    if ((err = pthread_mutex_unlock(&mtx)) != 0) {
        fprintf(stderr, "pthread_mutex_unlock(): %s", strerror(err));
        return 1;
    }

    printf("Unlocking mutex...\n");
    if ((err = pthread_mutex_unlock(&mtx)) != 0) {
        fprintf(stderr, "pthread_mutex_unlock(): %s", strerror(err));
        return 1;
    }

    printf("Destroying mutex...\n");
    if ((err = pthread_mutex_destroy(&mtx)) != 0) {
        fprintf(stderr, "pthread_mutex_destroy(): %s", strerror(err));
        return 1;
    }

    if ((err = pthread_mutexattr_destroy(&attr)) != 0) {
        fprintf(stderr, "pthread_mutex_init(): %s", strerror(err));
        return 1;
    }

    return 0;
}
