"""q598 Breakwater Grammar -- grouped relay language with a dormant first command."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HARBOR,SKIFF,CHANNEL,GROUP,RELAY,LATENT,BAD=8,10,12,14,15,13,6,3
LEVELS=[{"name":n,"cmd":c,"shift":s} for n,c,s in [("Cargo Pair",[[1,3]],0),("Channel Relay",[[2,4],[1,3]],1),("Grouped Route",[[4,2],[3,1]],2),("Dormant Wake",[[3,4],[1,2],[4,1]],1),("Two Subgoals",[[2,1],[4,3],[1,4]],3),("Breakwater Grammar",[[4,1],[2,3],[3,4],[1,2]],2)]]
def enc(a,s,g):return((a-1+s+g)%4)+1
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=HARBOR;f[13:24,8:22]=SKIFF;f[13:24,42:56]=SKIFF;f[29:34,8:56]=CHANNEL;f[40:44,8:8+len(g.buffer)*10]=GROUP;f[48:52,8:8+g.progress*11]=RELAY
  if g.first is not None:f[54:58,43:55]=LATENT
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q598(ARCBaseGame):
 def __init__(self):self.display=D(self);self.buffer=[];self.progress=self.subgoals=0;self.first=None;self.bad=False;ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q598",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.buffer=[];self.progress=self.subgoals=0;self.first=None;self.bad=False
 def step(self):
  z=self.action.id.value;x=LEVELS[self.level_index]
  if z==0:self.complete_action();return
  if z in (1,2,3,4):self.buffer.append(enc(z,x["shift"],self.progress));self.first=z if self.first is None else self.first
  elif z==5:
   if self.progress<len(x["cmd"]) and self.buffer==x["cmd"][self.progress]:self.progress+=1;self.buffer=[];self.subgoals=min(2,self.subgoals+1)
   else:self.bad=True;self.lose()
  elif z==6:
   expected=((x["cmd"][0][0]-1-x["shift"])%4)+1
   if self.progress==len(x["cmd"]) and self.subgoals==min(2,len(x["cmd"])) and self.first==expected:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
