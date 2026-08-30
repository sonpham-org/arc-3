"""q433 Impeller Revision -- recalibrate a worn rule while additional samples become costly."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,TURBINE,BLADE,WAKE,SAMPLE,WEAR,RULE,BAD=9,6,15,12,14,11,10,8
LEVELS=[
 {"name":"First Revision","old":0,"new":1,"boundary":1,"delay":0},{"name":"Rotated Wake","old":1,"new":2,"boundary":2,"delay":1},
 {"name":"Delayed Blade","old":2,"new":0,"boundary":3,"delay":2},{"name":"Costly Contrast","old":0,"new":2,"boundary":2,"delay":1},
 {"name":"Sparse Recheck","old":1,"new":0,"boundary":4,"delay":2},{"name":"Impeller Revision","old":2,"new":1,"boundary":5,"delay":1}]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;x=LEVELS[g.level_index];f[:,:]=BG;f[5:59,4:60]=TURBINE
  for i in range(3):f[12:26,9+i*17:20+i*17]=BLADE if g.evidence&(1<<i) else WAKE
  f[33:37,8:8+g.samples*12]=SAMPLE;f[41:45,8:8+g.wear*6]=WEAR;f[49:53,8:8+g.candidate*13]=RULE;f[55:59,8:8+g.delay*13]=WAKE
  if g.wear>=x["boundary"]:f[7:10,8:56]=WEAR
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q433(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.rule=self.wear=self.sample=self.evidence=self.samples=self.candidate=self.delay=0;self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q433",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.rule=LEVELS[self.level_index]["old"];self.wear=0;self.sample=-1;self.evidence=self.samples=self.candidate=self.delay=0;self.bad=False
 def advance(self):
  x=LEVELS[self.level_index];self.wear+=1
  if self.wear>=x["boundary"]:self.rule=x["new"]
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a==1:self.sample=self.rule;self.samples+=1;self.advance()
  elif a==2:self.advance()
  elif a==3:
   if self.sample>=0:self.evidence|=1<<self.sample;self.sample=-1
   else:self.bad=True;self.lose()
  elif a==4:self.candidate=(self.candidate+1)%3
  elif a==5:self.delay=(self.delay+1)%3
  elif a==6:
   need=(1<<x["old"])|(1<<x["new"])
   if self.evidence&need==need and self.samples==2 and self.candidate==x["new"] and self.delay==x["delay"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
