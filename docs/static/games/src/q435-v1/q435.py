"""q435 Vivarium Revision -- recalibrate worn strata while partner favor follows the inferred law."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,VIVARIUM,FAUNA,STRATA,SAMPLE,WEAR,FAVOR,BAD=9,14,15,12,11,10,13,8
LEVELS=[
 {"name":"First Revision","old":0,"new":1,"boundary":1},{"name":"Rotated Stratum","old":1,"new":2,"boundary":2},
 {"name":"Delayed Habitat","old":2,"new":0,"boundary":3},{"name":"Reciprocal Law","old":0,"new":2,"boundary":2},
 {"name":"Sparse Vivarium","old":1,"new":0,"boundary":4},{"name":"Vivarium Revision","old":2,"new":1,"boundary":5}]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;x=LEVELS[g.level_index];f[:,:]=BG;f[5:59,4:60]=VIVARIUM
  for i in range(3):f[12:26,9+i*17:20+i*17]=FAUNA if g.evidence&(1<<i) else STRATA
  f[34:38,8:8+g.wear*6]=WEAR;f[42:46,8:8+g.favor*14]=FAVOR;f[49:53,8:8+g.candidate*13]=SAMPLE
  if g.wear>=x["boundary"]:f[7:10,8:56]=WEAR
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q435(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.rule=self.wear=self.evidence=self.favor=self.candidate=0;self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q435",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.rule=LEVELS[self.level_index]["old"];self.wear=self.evidence=self.favor=self.candidate=0;self.bad=False
 def advance(self):
  x=LEVELS[self.level_index];self.wear+=1
  if self.wear>=x["boundary"]:self.rule=x["new"]
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a==1:self.evidence|=1<<self.rule;self.advance()
  elif a==2:self.advance()
  elif a==3:self.favor=(self.favor+self.rule+1)%3
  elif a==4:self.candidate=(self.candidate+1)%3
  elif a==5:self.favor=(self.favor+1)%3
  elif a==6:
   need=(1<<x["old"])|(1<<x["new"]);target=(x["new"]+1)%3
   if self.evidence&need==need and self.favor==target and self.candidate==x["new"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
