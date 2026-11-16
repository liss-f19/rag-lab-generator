
#include "channel.h"
#include "macros.h"

#include <errno.h>
#include <fcntl.h>
#include <linux/limits.h>
#include <semaphore.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

channel_t* channel_open(const char* path) {

    // Use sem_name to initialize semaphore accompanied by channel
    char sem_name[PATH_MAX] = "sem_";
    strncpy(sem_name + 4, path, PATH_MAX - 5);
    sem_name[PATH_MAX-1] = 0;

    // Implement stage 1 here
    UNUSED(path);

    return NULL;
}

void channel_close(channel_t* channel) {
    // Implement stage 1 here
    UNUSED(channel);
}

int channel_produce(channel_t* channel, const char* produced_data, uint16_t length) {
    // Implement stage 3 here
    UNUSED(channel);
    UNUSED(produced_data);
    UNUSED(length);

    return 0;
}

int channel_consume(channel_t* channel, char* consumed_data, uint16_t* length) {
    // Implement stage 2 here
    UNUSED(channel);
    UNUSED(consumed_data);
    UNUSED(length);

    return 0;
}
