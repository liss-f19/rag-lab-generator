# L1 Sample Task 4: Ἡ Βιβλιοθήκη τῆς Ἀλεξάνδρειας (The Library of Alexandria)

*Topic: L1 — Filesystem (sample task)*

*Starter files: [attachments/sop1l1e4.zip](attachments/sop1l1e4.zip)*


It is the third century BC. Callimachus of Cyrene (Καλλίμαχος ὁ Κυρηναῖος) has just completed his famous Pinakes (Πίνακες), a vast catalogue of hundreds of thousands of scrolls in the Library of Alexandria, in 120 volumes. It took an enormous amount of work, but as you might expect, such a large catalogue is still inconvenient to use. Callimachus is undeterred and is already thinking about another improvement to the Library’s resource indexing. For this, he plans to use the latest achievement of Hellenic technology: a computer running Λίνουξ operating system.

Callimachus will enter information about the scrolls into the computer. Your task is to write a program that runs on Λίνουξ and uses the ΠΟΣΙΞ API to create the appropriate indexes.

Remember to release all unused resources (memory and file descriptors), check system function errors, and follow good programming practices.

## Stages

### Stage 1

At this stage, the program takes one argument: the path to a file containing metadata for a book in the library. The metadata uses a simple format: each line contains a `key:value` pair. You may assume there are no extra `:` characters on a line, but you must handle other invalid input. Read the file and print the values of the `author`, `title`, and `genre` fields, in that order. If a field is missing, print `missing!` for it. For example, given a file containing:

```
uthor:Plutarch
latin_title:De fluviorum et montium nominibus et de iis, quae in illis inveniuntur
title:Περὶ ποταμῶν καὶ ὀρῶν ἐπωνυμίας
genre:geography
incipit:When Chrysippe, through the anger of Aphrodite
had fallen into a yearning
for Hydaspes
```

the program should print:

```
author: missing!
title: Περὶ ποταμῶν καὶ ὀρῶν ἐπωνυμίας
genre: geography
```

(The first line contains a typo, so the program does not find the `author` field.)

Hint: The standard library provides many useful functions for this kind of parsing, such as `getline`, `strchr`, `strcmp`, and `strdup`.

Hint 2: We will need this functionality again later, though not immediately, so it is best to put it in a separate function.

### Stage 2

Callimachus’s database mirrors the physical structure of the Great Library in its directory tree. Nested directories represent the building’s wings, rooms, shelves, racks, chests... At the end of this hierarchy are regular files whose names reflect the titles written on the outside of the scrolls (which need not match the actual book titles in the metadata).

Modify the program so it no longer takes arguments. When run, it recursively searches the `library` directory. All regular files represent books. Create an `index` directory in the program’s current directory (report an error if it already exists). Inside it, create a directory named `by-visible-title`. Put relative symbolic links there to all the books (files) in the library, using their names but without their nested directory structure. If any name is repeated, report an error.

### Stage 3

Create two new indexes alongside `by-visible-title`.

The `by-title` index is similar to the one from the previous stage, but uses the `title` metadata field as the filename. If the field is missing, skip the file. If the title is longer than 64 bytes, truncate it to that length.

The `by-genre` index places books in subdirectories of the form `index/by-genre/<genre>`, where `<genre>` is the value of the `genre` metadata field. Use the book’s metadata title as the filename, as above. Truncate the genre value to 64 bytes if necessary.

### Stage 4

The final index feature is checking that no books are missing. Another programmer has already created a file containing a list of all the books in binary format. At this stage, if provided, the program’s first argument is the path to this database file. Read its contents and check that no books are missing. The database format is as follows: it contains some number of entries, each consisting of 4 bytes representing the file size (`unsigned int`) and the first 64 bytes of the title (from the metadata). If the title is shorter than 64 bytes, the field is padded with zeros, so each entry is always 68 bytes; the number of entries can be determined from the file size. Scan the library. For every missing book, print `Book "<title>" is missing`; if the file size does not match, print `Book "<title>" size mismatch (<expected size> vs <file size>)`. Use `readv` to read the database. Use the `by-title` index to check whether books are missing.

The starter files contain two example databases. The first, `database_correct`, contains all books in the library directory. The second, `database_missing`, contains additional books, so the check should report an error.

Hint: To ensure the string is always null-terminated, you can use a 65-character array in the structure representing a single book and set the last character to zero. This way, even if the title has been truncated to the full 64 bytes, the string will still be null-terminated after reading it.
