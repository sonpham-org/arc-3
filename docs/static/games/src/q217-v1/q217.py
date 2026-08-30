"""q217 Catalyst Veil -- freeze an observed bead while hidden pipes evolve and stored views execute."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,REFINERY,PIPE,BEAD,FOCUS,MEMORY,GOAL,BAD=0,12,11,15,14,10,13,8
LEVELS=[
 {"name":"First Stored View","plan":(1,4)},{"name":"Hidden Pipe","plan":(2,5,4,1)},
 {"name":"Coupled Beads","plan":(3,4,2,5,4)},{"name":"Sightline Memory","plan":(1,5,2,4,3,4)},
 {"name":"Executed Veil","plan":(2,4,1,5,3,4,1)},{"name":"Catalyst Veil","plan":(3,5,1,4,2,5,4,1)}]
def advance(s,a):
 o,focus,stored=s;o=list(o);stored=list(stored)
 if a in (1,2,3):
  focus=a-1;stored[focus]=o[focus]
  for i in range(3):
   if i!=focus:o[i]=(o[i]+i+1)%4
 elif a==4:
  if stored[focus] is None:return None
  o[focus]=(o[focus]+stored[focus]+1)%4;stored[focus]=None
 else:o=[(v+1)%4 for v in o]
 return tuple(o),focus,tuple(stored)
def target(x):
 s=((0,1,2),0,(None,None,None))
 for a in x["plan"]:s=advance(s,a)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=REFINERY
  for i,v in enumerate(g.orientation):
   x=9+i*17;f[11:29,x:x+11]=PIPE;f[15+v*2:21+v*2,x+3:x+8]=BEAD
   if g.stored[i] is not None:f[32:36,x:x+11]=MEMORY
   if i==g.focus:f[8:11,x:x+11]=FOCUS
  f[51:56,8:8+sum(g.orientation)*5]=GOAL
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q217(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.orientation=(0,1,2);self.focus=0;self.stored=(None,None,None);self.target=target(LEVELS[0]);self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q217",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.orientation=(0,1,2);self.focus=0;self.stored=(None,None,None);self.target=target(LEVELS[self.level_index]);self.bad=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.orientation,self.focus,self.stored),a)
   if s is None:self.bad=True;self.lose()
   else:self.orientation,self.focus,self.stored=s
  elif a==6:
   if (self.orientation,self.focus,self.stored)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
