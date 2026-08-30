"""q133 Spatial Grammar -- order and arrangement jointly encode each command."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,PANEL,ORDER,ARRANGE,COMMAND,DONE,BAD=7,1,12,9,10,14,8
LEVELS=[
 {"name":"Order Word","items":[(0,0),(1,0)]}, {"name":"Arrangement Verb","items":[(0,1),(1,2),(2,3)]},
 {"name":"Two Dimensions","items":[(3,0),(1,2),(0,3),(2,1)]}, {"name":"Grammar Chain","items":[(0,2),(2,0),(1,3),(3,1),(2,2)]},
 {"name":"Nested Phrase","items":[(3,3),(0,1),(2,0),(1,2),(0,3),(3,1)]}, {"name":"Spatial Grammar","items":[(1,3),(3,0),(0,2),(2,1),(1,0),(3,2),(0,1)]}]
def decode(item):order,arr=item;return ((order+arr)%4)+1
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:55,4:60]=PANEL
  for i,(order,arr) in enumerate(g.items):
   x=8+i*7;f[14+order*3:17+order*3,x:x+5]=ORDER;f[31:36,x+arr:x+arr+2]=ARRANGE;f[43:49,x:x+5]=DONE if i<g.progress else COMMAND
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q133(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.items=[];self.progress=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q133",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4])
 def on_set_level(self,l):self.items=list(map(tuple,LEVELS[self.level_index]["items"]));self.progress=0;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a!=decode(self.items[self.progress]):self.failed=True;self.lose()
  else:
   self.progress+=1
   if self.progress==len(self.items):self.next_level()
  self.complete_action()
