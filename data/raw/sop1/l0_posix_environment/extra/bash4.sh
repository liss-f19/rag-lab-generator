#!/bin/bash

# Contents:
# 1. ARITHMETIC OPERATIONS
# 2. FOR LOOP
# 3. STRING CHOPPING


echo
echo "*** ARITHMETIC OPERATIONS ***"
echo


# Variable can store integer value...
TWO=2
# ... but how about arithmetic oparations?
FOUR=$TWO+$TWO 
echo $FOUR

# The `let' built-in allows computations
let FOUR=$TWO+$TWO
echo $FOUR 
# Alternatively, double brackets can be used
((SIX=$TWO+$FOUR))
echo $SIX

echo 

# Note that for `((' we can check return status...
((2+2))
echo $?
((2<3))
echo $?
((2>3))
echo $?
# ... or the value
echo $((2+2))


echo
echo "*** FOR LOOP ***"
echo


# Let's introduce the `for' loop
i=1
for filename in `ls /`
do
	echo "$i : /$filename"
	let i++
done

echo

# The other form of `for' uses C-like syntax
for ((i=0; i<4; i++)); do echo $i; done


echo
echo "*** STRING CHOPPING ***"
echo


# We can easily separate a path name and a file name having a full path name
SOMEFILE="/home/smithj/somefile"
echo $SOMEFILE
basename $SOMEFILE
dirname $SOMEFILE

echo

# We can also chop strings with `#' and `%'
STRING="abcdcba"
echo $STRING
echo ${STRING#*c}
echo ${STRING##*c}
echo ${STRING%c*}
echo ${STRING%%c*}
