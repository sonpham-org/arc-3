#!/bin/bash
# Launch the context-window grid (3-Oct-2026): 3 full runs per slot count (1 at 10 slots: 2 exist as hicache-sb11-a/b).
cd /d/codex-work/daniel-draft
N=gs://cellens-ai-artifacts/arc3-duck/daniel-base/notebooks
declare -A NB=([7]=5c1be125c75d [8]=0662d6ed3036 [9]=2b06599bb708 [10]=951565505d76 [12]=3feace8ba8d7 [14]=7432ce7a564f [16]=7e5982d5dde4 [18]=6da0862c09c5 [20]=202c7c9b8e2c [22]=ffb3d0df5987)
Z=(us-west4-a us-south1-a us-east4-b us-south1-b us-east5-c us-east4-c us-west1-b us-east5-b us-west1-a)   # us-central1 reserved for the RL loop (Son, 4-Oct)
i=0
for s in 7 8 9 10 12 14 16 18 20 22; do
  reps="a b c"; [ $s = 10 ] && reps="c"
  for rep in $reps; do
    zs=("${Z[@]:$((i % ${#Z[@]}))}" "${Z[@]:0:$((i % ${#Z[@]}))}")
    lab=$(printf "s%02d-%s-1003" $s $rep)
    bash launch_ctx_run.sh $lab $N/${NB[$s]}/notebook.ipynb "${zs[@]}" > /tmp/ctx-$lab.out 2>&1 &
    i=$((i+1))
    [ $((i % 7)) = 0 ] && wait
  done
done
wait
cat /tmp/ctx-s*-1003.out | grep -E "^launched|^[a-z0-9-]+:" | sort
