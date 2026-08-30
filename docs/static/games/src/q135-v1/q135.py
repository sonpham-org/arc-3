"""q135 Parity Signals -- decode grouped pulse parity rather than raw count."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,PANEL,PULSE,GROUP,OUTPUT,DONE,BAD=7,1,12,10,9,14,8
LEVELS=[
 {"name":"Odd Group","groups":[(1,2),(2,2)]}, {"name":"Two Parities","groups":[(1,1),(2,3),(3,2)]},
 {"name":"Grouped Code","groups":[(3,3),(4,1),(2,4),(1,2)]}, {"name":"Error Check","groups":[(4,4),(3,2),(2,1),(1,3),(3,4)]},
 {"name":"Parity Phrase","groups":[(1,4),(2,3),(4,2),(3,1),(2,2),(1,1)]}, {"name":"Parity Signals","groups":[(3,4),(4,3),(1,2),(2,1),(3,3),(4,4),(1,1)]}]
def decode(g):a,b=g;return (a%2)*2+(b%2)+1
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:56,4:60]=PANEL
  for i,(a,b) in enumerate(g.groups):x=7+i*8;f[14:18,x:x+a]=PULSE;f[22:26,x:x+b]=PULSE;f[29:32,x:x+6]=GROUP;f[39:46,x:x+6]=DONE if i<g.progress else OUTPUT
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q135(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.groups=[];self.progress=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q135",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4])
 def on_set_level(self,l):self.groups=list(map(tuple,LEVELS[self.level_index]["groups"]));self.progress=0;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a!=decode(self.groups[self.progress]):self.failed=True;self.lose()
  else:
   self.progress+=1
   if self.progress==len(self.groups):self.next_level()
  self.complete_action()
