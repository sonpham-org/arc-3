"""q434 Tessera Revision -- sample both sides of wear, then interrupt a compressed seam routine."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,MOSAIC,TESSERA,SEAM,SAMPLE,WEAR,RULE,BAD=9,7,15,12,14,11,10,8
LEVELS=[
 {"name":"First Revision","old":0,"new":1,"boundary":1,"period":4,"macros":0},{"name":"Rotated Seam","old":1,"new":2,"boundary":2,"period":5,"macros":0},
 {"name":"Delayed Fold","old":2,"new":0,"boundary":3,"period":6,"macros":1},{"name":"Macro Contrast","old":0,"new":2,"boundary":2,"period":7,"macros":1},
 {"name":"Sparse Mosaic","old":1,"new":0,"boundary":4,"period":8,"macros":1},{"name":"Tessera Revision","old":2,"new":1,"boundary":5,"period":9,"macros":2}]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;x=LEVELS[g.level_index];f[:,:]=BG;f[5:59,4:60]=MOSAIC
  for i in range(3):f[12:26,9+i*17:20+i*17]=TESSERA if g.evidence&(1<<i) else SEAM
  f[33:37,8:29 if g.caught else 16]=SAMPLE;f[41:45,8:8+g.wear*5]=WEAR;f[49:53,8:8+g.candidate*13]=RULE
  if g.wear>=x["boundary"]:f[7:10,8:56]=WEAR
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q434(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.rule=self.wear=self.evidence=self.candidate=0;self.caught=False;self.history=[];self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q434",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.rule=LEVELS[self.level_index]["old"];self.wear=self.evidence=self.candidate=0;self.caught=False;self.history=[];self.bad=False
 def advance(self,n):
  x=LEVELS[self.level_index];self.wear+=n
  if self.wear>=x["boundary"]:self.rule=x["new"]
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a==1:self.evidence|=1<<self.rule;self.advance(1);self.history.append(a)
  elif a==2:self.advance(1);self.history.append(a)
  elif a==3:self.advance(3);self.history.append(a)
  elif a==4:self.caught|=self.wear%x["period"]==(x["boundary"]+1+3*x["macros"])%x["period"];self.history.append(a)
  elif a==5:self.candidate=(self.candidate+1)%3
  elif a==6:
   need=(1<<x["old"])|(1<<x["new"]);plan=(1,)+(2,)*(x["boundary"]-1)+(1,)+(3,)*x["macros"]+(4,)
   if tuple(self.history)==plan and self.evidence&need==need and self.caught and self.candidate==x["new"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
