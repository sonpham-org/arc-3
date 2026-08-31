"""q379 Monsoon Rig -- build a dual-effect rain tool before the weather cycles align."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GARDEN,CLOUD,RAIN,PART,RIG,CYCLE,ROUTE,BAD=5,10,9,14,6,12,11,7,15
def repeat(n):return tuple((i%4)+1 for i in range(n))+(5,)
LEVELS=[{"name":"Rain Hook","periods":(2,2),"plan":(1,4,5)},{"name":"Joined Gutter","periods":(3,3),"plan":(2,1,4,5)},{"name":"Nested Driver","periods":(2,4),"plan":(3,2,1,4,5)},{"name":"Unequal Rig","periods":(2,3),"plan":(1,3,4,2,1,4,5)},{"name":"Long Assembly","periods":(3,4),"plan":repeat(12)},{"name":"Monsoon Rig","periods":(4,5),"plan":repeat(20)}]
def advance(s,a,x):
 parts,rig,pa,pb,builds,route=s;parts=list(parts)
 if a in (1,2,3,4):
  if a in (1,2,3):parts[a-1]+=1
  else:
   if not sum(parts):return None
   rig=(sum((i+1)*v for i,v in enumerate(parts))+pa+pb)%8;parts=[0,0,0];builds+=1
  pa=(pa+1)%x["periods"][0];pb=(pb+1)%x["periods"][1]
 elif a==5:
  if pa or pb or rig is None:return None
  route=(rig+builds)%5
 return tuple(parts),rig,pa,pb,builds,route
def target(x):
 s=((0,0,0),None,0,0,0,0)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=GARDEN
  for i,v in enumerate(g.parts):x=8+i*18;f[8:31,x:x+14]=CLOUD;f[26-v*4:28,x+4:x+10]=PART+i
  f[35:42,8:18+(g.rig or 0)*5]=RIG;f[47:50,8:24]=CYCLE;f[54:57,8:11+g.route*10]=ROUTE
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q379(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q379",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.parts=(0,0,0);self.rig=None;self.pa=self.pb=self.builds=self.route=0
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.parts,self.rig,self.pa,self.pb,self.builds,self.route),a,x)
   if s is None:self.bad=True;self.lose()
   else:self.parts,self.rig,self.pa,self.pb,self.builds,self.route=s
  elif a==6:
   if (self.parts,self.rig,self.pa,self.pb,self.builds,self.route)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
