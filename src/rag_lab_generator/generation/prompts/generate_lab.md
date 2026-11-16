Write a new laboratory task for the course {course} about: {topic}.

The task must match the style, size and difficulty of the reference tasks below. Target
difficulty: {difficulty}. Reference labs: {based_on}

Retrieved course material (tutorial sections, example tasks, lecture fragments):

---
{context}
---

Requirements:

1. Use only the POSIX APIs, headers, macros and conventions that appear in the retrieved material.
   Do not introduce a function that the referenced tutorial sections do not teach.
2. Output markdown with exactly this structure:

   - a level-1 heading with a short title,
   - `## Description`: one paragraph describing the exact behaviour of the program: what it reads,
     what it writes, the error handling it must do; then the positional argument list, one argument
     per line with a one-line meaning; then an example run inside a fenced code block showing the
     command line and the expected output.
   - `## Stages`: a numbered list of 4 to 6 stages. Every stage says what to implement in that step
     and finishes with `To show:` followed by how the student demonstrates it to the teacher
     (which command to run, with which arguments, what must appear on screen).

3. Stages grow monotonically: stage 1 is a few lines of code, the last stage is the complete
   program. Each stage must be demonstrable on its own.
4. Keep the language of the reference tasks: imperative, precise, no motivation, no solution code.
5. Mention error handling explicitly (checking return values, `errno`, releasing resources) the way
   the course requires it.
