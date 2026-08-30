"""q432 Semaphore Revision -- compare two miniature systems across a learnable wear boundary."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CLIFF,FLAG,BEAM,SAMPLE,WEAR,RULE,BAD=9,13,15,14,11,12,10,8
LEVELS=[
 {"name":"First Revision","old":0,"new":1,"boundary":1,"delay":0},{"name":"Rotated Law","old":1,"new":2,"boundary":2,"delay":1},
 {"name":"Delayed Relay","old":2,"new":0,"boundary":3,"delay":2},{"name":"Dual Test","old":0,"new":2,"boundary":2,"delay":1},
 {"name":"Sparse Calibration","old":1,"new":0,"boundary":4,"delay":2},{"name":"Semaphore Revision","old":2,"new":1,"boundary":5,"delay":1}]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;x=LEVELS[g.level_index];f[:,:]=BG;f[5:59,4:60]=CLIFF
  f[11:25,9:25]=FLAG if g.systems&1 else BEAM;f[11:25,39:55]=FLAG if g.systems&2 else BEAM
  for i in range(3):f[31:39,9+i*17:21+i*17]=SAMPLE if g.evidence&(1<<i) else CLIFF
  f[44:48,8:8+min(g.wear,7)*6]=WEAR;f[50:54,8:8+g.candidate*13]=RULE;f[56:60,8:8+g.delay*13]=BEAM
  if g.wear>=x["boundary"]:f[7:10,8:56]=WEAR
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q432(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.rule=self.wear=self.evidence=self.systems=self.candidate=self.delay=0;self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q432",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):
  self.rule=LEVELS[self.level_index]["old"];self.wear=self.evidence=self.systems=self.candidate=self.delay=0;self.bad=False
 def advance(self):
  x=LEVELS[self.level_index];self.wear+=1
  if self.wear>=x["boundary"]:self.rule=x["new"]
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2):self.evidence|=1<<self.rule;self.systems|=1<<(a-1);self.advance()
  elif a==3:self.advance()
  elif a==4:self.candidate=(self.candidate+1)%3
  elif a==5:self.delay=(self.delay+1)%3
  elif a==6:
   need=(1<<x["old"])|(1<<x["new"])
   if self.evidence&need==need and self.systems==3 and self.candidate==x["new"] and self.delay==x["delay"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
