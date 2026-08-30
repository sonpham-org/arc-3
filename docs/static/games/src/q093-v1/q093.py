"""q093 Milestone Garden -- stable intermediate patterns unlock new growth operations."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SOIL,SEED,GROW,MILESTONE,TARGET,CURSOR,BAD=15,12,6,14,9,11,10,8
LEVELS=[
 {"name":"First Milestone","target":3,"ops":[1,2],"gates":[(1,2)]},
 {"name":"Unlock Growth","target":7,"ops":[1,2,4],"gates":[(1,2),(3,3)]},
 {"name":"Stable Pattern","target":15,"ops":[1,2,4,8],"gates":[(1,2),(3,3),(7,4)]},
 {"name":"Garden Ladder","target":31,"ops":[1,2,4,8,16],"gates":[(1,2),(3,3),(7,4),(15,5)]},
 {"name":"Delayed Bloom","target":47,"ops":[1,2,4,8,16,32],"gates":[(1,2),(3,3),(7,4),(15,5),(31,6)]},
 {"name":"Milestone Garden","target":63,"ops":[1,2,4,8,16,32],"gates":[(1,2),(3,3),(7,4),(15,5),(31,6)]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=SOIL
  for i in range(6):
   x=8+(i%3)*18;y=14+(i//3)*20;bit=1<<i;f[y:y+11,x:x+11]=GROW if g.mask&bit else SEED;f[y+3:y+8,x+3:x+8]=TARGET if g.target&bit else SOIL
  for i,op in enumerate(g.ops):f[58:62,5+i*9:12+i*9]=CURSOR if i==g.cursor else MILESTONE if i<g.unlocked else SEED
  if g.failed:f[2:6,25:39]=BAD
  return f
class Q093(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.target=0;self.ops=[];self.gates=[];self.mask=self.cursor=0;self.unlocked=1;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q093",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[3,4,5,6])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.target=s["target"];self.ops=list(s["ops"]);self.gates=list(s["gates"]);self.mask=self.cursor=0;self.unlocked=1;self.failed=False
 def refresh(self):
  for pattern,count in self.gates:
   if self.mask&pattern==pattern:self.unlocked=max(self.unlocked,count)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a==3:self.cursor=(self.cursor-1)%self.unlocked
  elif a==4:self.cursor=(self.cursor+1)%self.unlocked
  elif a==5:self.mask^=self.ops[self.cursor];self.refresh()
  elif a==6:
   if self.mask==self.target:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
