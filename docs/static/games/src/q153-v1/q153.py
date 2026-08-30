"""q153 Braids to Signals -- transfer crossing permutations into temporal channels."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,PANEL,STRAND,CROSS,SIGNAL,DONE,BAD=10,1,6,12,9,14,8
LEVELS=[
 {"name":"One Crossing","swaps":[0],"signals":[0,1]}, {"name":"Two Crossings","swaps":[1,0],"signals":[0,2,1]},
 {"name":"Braid Order","swaps":[0,2,1],"signals":[3,0,2,1]}, {"name":"Temporal Transfer","swaps":[2,0,1,2],"signals":[0,1,3,2,0]},
 {"name":"Interleaved Channels","swaps":[1,2,0,1,2],"signals":[3,1,0,2,3,0]}, {"name":"Braids to Signals","swaps":[0,2,1,0,2,1],"signals":[0,3,1,2,0,2,3]}]
def permutation(swaps):
 p=[0,1,2,3]
 for i in swaps:p[i],p[i+1]=p[i+1],p[i]
 return p
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[6:56,4:60]=PANEL
  xs=[11,24,37,50]
  for x in xs:f[10:34,x-1:x+2]=STRAND
  for row,i in enumerate(g.swaps):
   y=13+row*4;x0,x1=xs[i],xs[i+1];f[y:y+3,x0:x1+2]=CROSS
  for i,s in enumerate(g.signals):x=7+i*8;f[42:49,x:x+6]=DONE if i<g.progress else SIGNAL;f[44:47,x:x+s+2]=STRAND
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q153(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.swaps=self.signals=[];self.mapping=[];self.progress=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q153",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.swaps=list(s["swaps"]);self.signals=list(s["signals"]);self.mapping=permutation(self.swaps);self.progress=0;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a!=self.mapping[self.signals[self.progress]]+1:self.failed=True;self.lose()
  else:
   self.progress+=1
   if self.progress==len(self.signals):self.next_level()
  self.complete_action()
