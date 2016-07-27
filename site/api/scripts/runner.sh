#! /bin/bash
# script for running batches of parsing jobs
die() {
    echo >&2 "$@"
    echo ""
    echo Usage: runner.sh DIR
    exit 1
}

[ "$#" -eq 1 ] || die "1 argument required, $# provided"
[ -d "$1" ] || die "argument must be a directory"

DIR="$1"
START=0
END=$(ls -l "$DIR" | wc -l)
BATCH_SIZE=30

echo $DIR
while [ $START -lt $END ]
    do
        NEXT=$[$START+$BATCH_SIZE]
        if [ $NEXT -gt $END ]
            then
                NEXT=$[$END]
        fi
        python api/scripts/parser.py -d "$DIR" -s $START -e $NEXT
        # echo parse files $START to $[$NEXT-1]
        START=$NEXT
    done

exit 0
