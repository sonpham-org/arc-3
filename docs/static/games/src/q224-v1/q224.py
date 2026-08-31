"""q224 Tessera Veil -- interrupt an occlusion macro at a state-defined seam window."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,MOSAIC,SEAM,TILE,FOCUS,PHASE,INTERRUPT,GOAL,BAD=0,10,4,14,2,8,11,15,13
LEVELS=[{"name":"First Fold","window":1,"plan":(1,4,5)},{"name":"Second Seam","window":2,"plan":(2,4,4,5)},{"name":"Long Occlusion","window":3,"plan":(3,4,4,4,5)},{"name":"Early Interruption","window":1,"plan":(1,4,5,2,4)},{"name":"Topology Return","window":2,"plan":(2,4,4,5,3,1,4)},{"name":"Tessera Veil","window":3,"plan":(3,4,4,4,5,1,2,4,4,4,5)}]
def advance(s,a,x):
 cells,focus,seam,phase,interrupts=s;cells=list(cells)
 if a in (1,2,3):
  focus=a-1
  for i in range(3):
   if i!=focus:cells[i]=(cells[i]+i+seam+1)%4
 elif a==4:
  phase=(phase+1)%4
  for i in range(3):
   if i!=focus:cells[i]=(cells[i]+phase+seam+i)%4
  if phase==0:seam=1-seam
 elif a==5:
  if phase!=x["window"]:return None
  cells.reverse();seam=1-seam;phase=0;interrupts+=1
 return tuple(cells),focus,seam,phase,interrupts
def target(x):
 s=((0,1,2),0,0,0,0)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=MOSAIC
  for i,v in enumerate(g.cells):x=8+i*18;f[10:38,x:x+14]=SEAM;f[15+v*5:22+v*5,x+4:x+10]=TILE-i
  f[7:10,8+g.focus*18:22+g.focus*18]=FOCUS;f[43:46,8:11+g.phase*12]=PHASE;f[50:53,8:11+g.interrupts*10]=INTERRUPT;f[56:59,8:20]=GOAL
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q224(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q224",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.cells=(0,1,2);self.focus=self.seam=self.phase=self.interrupts=0
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.cells,self.focus,self.seam,self.phase,self.interrupts),a,x)
   if s is None:self.bad=True;self.lose()
   else:self.cells,self.focus,self.seam,self.phase,self.interrupts=s
  elif a==6:
   if (self.cells,self.focus,self.seam,self.phase,self.interrupts)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
