"""q430 Orchard Season -- bank observations while observation advances the season."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ORCHARD,SEASON,SAMPLE,BANK,SHELTER,RULE,BAD=9,14,12,15,11,10,6,8
LEVELS=[
 {"name":"First Season","boundary":1,"old":0,"new":1},{"name":"Late Harvest","boundary":2,"old":1,"new":2},
 {"name":"Sheltered Graft","boundary":3,"old":2,"new":0},{"name":"Moving Calendar","boundary":2,"old":0,"new":2},
 {"name":"Observed Revision","boundary":4,"old":1,"new":0},{"name":"Orchard Season","boundary":5,"old":2,"new":1}]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=ORCHARD;f[11:18,8:8+g.season*8]=SEASON
  for i in range(3):f[27:37,10+i*16:21+i*16]=BANK if g.evidence&(1<<i) else SAMPLE
  f[45:50,8:29 if g.sheltered else 16]=SHELTER;f[53:57,8:8+g.candidate*14]=RULE
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q430(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.season=self.rule=self.sample=self.evidence=self.candidate=0;self.sheltered=self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q430",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):
  x=LEVELS[self.level_index];self.season=0;self.rule=x["old"];self.sample=-1;self.evidence=self.candidate=0;self.sheltered=self.bad=False
 def advance(self):
  x=LEVELS[self.level_index];self.season+=1
  if self.season>=x["boundary"]:self.rule=x["new"]
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a==1:self.advance()
  elif a==2:self.sheltered=True;self.season=0
  elif a==3:self.sample=self.rule;self.advance()
  elif a==4:
   if self.sample>=0:self.evidence|=1<<self.sample;self.sample=-1
   else:self.bad=True;self.lose()
  elif a==5:self.candidate=(self.candidate+1)%3
  elif a==6:
   need=(1<<x["old"])|(1<<x["new"])
   if self.evidence&need==need and self.sheltered and self.candidate==x["new"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
