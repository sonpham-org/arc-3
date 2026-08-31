"""q380 Workbench Rig -- assemble reusable tools while repaying the actual helper."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,BENCH,FIXTURE,TOOL,PART,RIG,DEBT,ROUTE,BAD=5,10,9,14,6,12,11,7,15
LEVELS=[{"name":"Borrowed Clamp","plan":(1,4,5)},{"name":"Joined Driver","plan":(2,1,4,1,5)},{"name":"Offset Gauge","plan":(3,2,4,2,5)},{"name":"Two Helpers","plan":(1,4,2,4,2,5,1,5)},{"name":"Crossed Assembly","plan":(2,1,4,3,4,3,5,1,5)},{"name":"Workbench Rig","plan":(1,2,3,4,2,1,4,1,5,3,5)}]
def advance(s,a):
 parts,selected,debt,rig,builds,route=s;parts=list(parts);debt=list(debt)
 if a in (1,2,3):selected=a-1;parts[selected]+=1
 elif a==4:
  if not sum(parts):return None
  rig=(sum((i+1)*v for i,v in enumerate(parts))+builds+selected)%8;parts=[0,0,0];debt[selected]+=1;builds+=1
 elif a==5:
  if not debt[selected] or rig is None:return None
  debt[selected]-=1;route=(rig+builds+selected)%5
 return tuple(parts),selected,tuple(debt),rig,builds,route
def target(x):
 s=((0,0,0),0,(0,0,0),None,0,0)
 for a in x["plan"]:s=advance(s,a);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=BENCH
  for i,v in enumerate(g.parts):x=8+i*18;f[8:31,x:x+14]=FIXTURE;f[26-v*4:28,x+4:x+10]=PART+i;f[33:36,x:x+g.debt[i]*6]=DEBT
  f[40:47,8:18+(g.rig or 0)*5]=RIG;f[53:56,8:11+g.route*10]=ROUTE
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q380(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q380",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.parts=(0,0,0);self.selected=0;self.debt=(0,0,0);self.rig=None;self.builds=self.route=0
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.parts,self.selected,self.debt,self.rig,self.builds,self.route),a)
   if s is None:self.bad=True;self.lose()
   else:self.parts,self.selected,self.debt,self.rig,self.builds,self.route=s
  elif a==6:
   if (self.parts,self.selected,self.debt,self.rig,self.builds,self.route)==self.target and not sum(self.debt):self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
