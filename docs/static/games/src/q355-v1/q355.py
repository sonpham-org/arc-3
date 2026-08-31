"""q355 Alloy Rig -- assemble dual-effect foundry tools in a moving local frame."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FOUNDRY,LANE,BILLET,PART,RIG,FRAME,ROUTE,BAD=5,10,9,14,6,12,11,7,15
LEVELS=[{"name":"First Redirect","plan":(1,4,5)},{"name":"Joined Force","plan":(2,1,4,5)},{"name":"Rotated Support","plan":(3,2,4,1,5)},{"name":"Dual Effect","plan":(1,3,2,4,5)},{"name":"Translated Rig","plan":(2,1,4,3,4,5)},{"name":"Alloy Rig","plan":(3,1,2,4,3,1,4,5)}]
def advance(s,a):
 parts,rig,rotation,offset,route=s;parts=list(parts)
 if a in (1,2,3):i=(a-1+rotation)%3;parts[i]+=1;route=(route+a+parts[i]+offset)%5
 elif a==4:
  if not sum(parts):return None
  rig+=1;route=(route+parts[0]*2+parts[1]*3+parts[2]+rotation+offset)%5;parts=[max(0,v-1) for v in parts];rotation=(rotation+1)%4;offset=(offset+1)%5
 elif a==5:route=(route+rig+rotation+offset)%5
 return tuple(parts),rig,rotation,offset,route
def target(x):
 s=((0,0,0),0,0,0,0)
 for a in x["plan"]:s=advance(s,a);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FOUNDRY;f[8:15,8:56]=LANE
  for i,n in enumerate(g.parts):x=9+i*17;f[19:22,x:x+11]=PART+i;f[24:24+n*6,x:x+11]=BILLET-i
  for i in range(g.rig):f[41+i*4:44+i*4,10:54]=RIG
  f[50:53,8:11+g.rotation*11]=FRAME;f[54:57,8:11+g.offset*9]=FRAME;f[58:60,8:11+g.route*10]=ROUTE
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q355(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q355",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.parts=(0,0,0);self.rig=self.rotation=self.offset=self.route=0
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.parts,self.rig,self.rotation,self.offset,self.route),a)
   if s is None:self.bad=True;self.lose()
   else:self.parts,self.rig,self.rotation,self.offset,self.route=s
  elif a==6:
   if (self.parts,self.rig,self.rotation,self.offset,self.route)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
