"""q423 Frostline Amendment -- detect a wear-triggered rule change after carrier exchange."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ICE,WEAR,SAMPLE,CARRIER,RULE,BAD=7,10,12,15,14,6,8
LEVELS=[{"name":n,"boundary":b,"old":o,"new":r} for n,b,o,r in [
 ("First Thaw",1,0,1),("Delayed Melt",2,1,2),("Carrier Crack",3,2,0),
 ("Moving Frostline",2,0,2),("Rule Amendment",4,1,0),("Frostline Amendment",5,2,1)]]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,5:59]=ICE;f[12:18,8:8+g.wear*8]=WEAR
  f[25:34,11:25]=CARRIER if not g.swapped else RULE
  for i in range(3):f[40:47,10+i*16:21+i*16]=SAMPLE if g.evidence&(1<<i) else ICE
  f[52:56,8:8+g.candidate*14]=RULE
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q423(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.wear=self.rule=self.evidence=self.candidate=0;self.swapped=self.bad=False
  levels=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS]
  super().__init__("q423",levels,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,6])
 def on_set_level(self,l):
  x=LEVELS[self.level_index];self.wear=0;self.rule=x["old"];self.evidence=self.candidate=0;self.swapped=self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a==1:
   self.wear+=1
   if self.wear>=x["boundary"]:self.rule=x["new"]
  elif a==2:self.evidence|=1<<self.rule
  elif a==3:self.candidate=(self.candidate+1)%3
  elif a==4:self.swapped=True;self.wear=0
  elif a==6:
   needed=(1<<x["old"])|(1<<x["new"])
   if self.evidence&needed==needed and self.candidate==x["new"] and self.swapped:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
