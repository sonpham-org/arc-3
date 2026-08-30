"""q156 Bridge Logic -- transfer AND/OR bridge structure into invisible activation logic."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,RIVER,BRIDGE,AND,OR,INPUT,OUTPUT,CURSOR,BAD=9,10,3,12,15,6,14,11,8
LEVELS=[
 {"name":"Conjunction Bridge","gates":[(0,1,1)]},
 {"name":"Disjunction Span","gates":[(1,1,0),(0,1,1)]},
 {"name":"Logic Transfer","gates":[(0,1,1),(1,0,0),(0,1,0)]},
 {"name":"Invisible Supports","gates":[(1,0,1),(0,1,1),(1,0,0),(0,1,0)]},
 {"name":"Mixed Structure","gates":[(0,1,1),(1,0,1),(1,0,0),(0,1,0),(1,1,0)]},
 {"name":"Bridge Logic","gates":[(1,0,1),(0,1,1),(1,1,0),(0,1,0),(1,0,0),(0,1,1)]}]
def evaluate(gate):op,a,b=gate;return int(bool(a and b) if op==0 else bool(a or b))
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=RIVER;n=len(g.gates)
  for i,gate in enumerate(g.gates):x=7+i*(50//n);f[19:30,x:x+8]=AND if gate[0]==0 else OR;f[33:38,x:x+8]=BRIDGE;f[41:47,x:x+8]=OUTPUT if g.values[i]==1 else INPUT if g.values[i]==0 else RIVER;f[14:17,x:x+8]=CURSOR if i==g.cursor else RIVER
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q156(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.gates=[];self.values=[];self.cursor=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q156",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,6])
 def on_set_level(self,l):self.gates=list(map(tuple,LEVELS[self.level_index]["gates"]));self.values=[-1]*len(self.gates);self.cursor=0;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2):self.values[self.cursor]=z-1
  elif z==3:self.cursor=(self.cursor-1)%len(self.gates)
  elif z==4:self.cursor=(self.cursor+1)%len(self.gates)
  elif z==6:
   if self.values==[evaluate(g) for g in self.gates]:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
