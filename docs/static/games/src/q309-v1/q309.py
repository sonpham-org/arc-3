"""q309 Reedbed Ledger -- conserve salinity while each transfer rewires the marsh route."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,MARSH,REED,SALT,LINK,LEDGER,GOAL,BAD=3,14,11,15,12,10,9,8
LEVELS=[
 {"name":"First Transfer","stock":4,"plan":(1,)},{"name":"Rewired Pair","stock":5,"plan":(1,2)},
 {"name":"Global Salinity","stock":6,"plan":(2,3,1)},{"name":"Obstructed Marsh","stock":7,"plan":(1,3,2,1)},
 {"name":"Conserved Route","stock":8,"plan":(2,1,3,2,1)},{"name":"Reedbed Ledger","stock":9,"plan":(1,2,3,1,3,2)}]
def advance(s,a):
 bins,link=s;b=list(bins);src=(a-1+link)%3;dst=(src+a)%3
 if b[src]:b[src]-=1;b[dst]+=1
 link=(link+a+b[dst])%3;return tuple(b),link
def target(x):
 s=((x["stock"],0,0),0)
 for a in x["plan"]:s=advance(s,a)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=MARSH
  for i,v in enumerate(g.bins):
   x=8+i*17;f[11:39,x:x+11]=REED;f[36-v*3:37,x+2:x+9]=SALT
  f[44:48,8:8+g.link*14]=LINK;f[51:55,8:8+sum(g.bins)*4]=LEDGER;f[57:60,8:8+sum(g.target[0])*4]=GOAL
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q309(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bins=(4,0,0);self.link=0;self.target=((4,0,0),0);self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q309",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):
  x=LEVELS[self.level_index];self.bins=(x["stock"],0,0);self.link=0;self.target=target(x);self.bad=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3):self.bins,self.link=advance((self.bins,self.link),a)
  elif a==4:self.link=(self.link+1)%3
  elif a==5:self.link=(self.link-1)%3
  elif a==6:
   if (self.bins,self.link)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
