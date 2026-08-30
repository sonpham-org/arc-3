"""q424 Bloom Calendar -- archive evidence across a season-triggered rule revision."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GARDEN,BLOOM,SEASON,SAMPLE,ARCHIVE,RULE,BAD=9,14,6,11,15,12,10,8
LEVELS=[{"name":n,"boundary":b,"old":o,"new":r} for n,b,o,r in [
 ("First Season",1,0,1),("Late Bloom",2,1,2),("Grafted Month",3,2,0),
 ("Moving Calendar",2,0,2),("Archived Revision",4,1,0),("Bloom Calendar",5,2,1)]]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=GARDEN
  for i in range(6):
   x=8+i*8;f[13:23,x:x+6]=BLOOM if i<g.season else GARDEN
  for i in range(3):f[31:39,10+i*16:21+i*16]=ARCHIVE if g.evidence&(1<<i) else SAMPLE
  f[47:52,8:29 if g.grafted else 16]=SEASON;f[53:57,8:8+g.candidate*14]=RULE
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q424(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.season=self.rule=self.sample=self.evidence=self.candidate=0;self.grafted=self.bad=False
  levels=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS]
  super().__init__("q424",levels,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):
  x=LEVELS[self.level_index];self.season=0;self.rule=x["old"];self.sample=-1;self.evidence=self.candidate=0;self.grafted=self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a==1:
   self.season+=1
   if self.season>=x["boundary"]:self.rule=x["new"]
  elif a==2:self.sample=self.rule
  elif a==3:self.grafted=True
  elif a==4:self.candidate=(self.candidate+1)%3
  elif a==5:
   if self.sample>=0:self.evidence|=1<<self.sample;self.sample=-1
   else:self.bad=True;self.lose()
  elif a==6:
   need=(1<<x["old"])|(1<<x["new"])
   if self.evidence&need==need and self.grafted and self.candidate==x["new"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
