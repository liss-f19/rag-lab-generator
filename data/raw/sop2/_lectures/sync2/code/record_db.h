#ifndef RECORD_DB_H
#define RECORD_DB_H

#include <pthread.h>

#define SHM_NAME "/record.db"
#define NUM_RECORDS 5

typedef struct {
    pthread_mutex_t mtx;
    int id;
    long long base_value;
    long long last_result;
    int processing_count;
} Record;

typedef struct {
#ifdef RECORD_DB_GLOBAL_LOCK
    pthread_mutex_t global_mtx;
#endif
    Record records[NUM_RECORDS];
} RecordDB;

static inline int record_db_lock(RecordDB *db, Record *record)
{
#ifndef RECORD_DB_GLOBAL_LOCK
    (void)db;
    return pthread_mutex_lock(&record->mtx);
#else
    (void)record;
    return pthread_mutex_lock(&db->global_mtx);
#endif
}

static inline int record_db_unlock(RecordDB *db, Record *record)
{
#ifndef RECORD_DB_GLOBAL_LOCK
    (void)db;
    return pthread_mutex_unlock(&record->mtx);
#else
    (void)record;
    return pthread_mutex_unlock(&db->global_mtx);
#endif
}

#endif
