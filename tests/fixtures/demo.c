#include <dirent.h>
#include <stdio.h>

int main(void) {
    DIR *dir = opendir(".");
    if (dir == NULL) {
        perror("opendir");
        return 1;
    }
    closedir(dir);
    return 0;
}
