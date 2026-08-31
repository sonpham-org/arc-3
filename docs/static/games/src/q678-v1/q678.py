"""q678 Escapement Analogy -- transfer gear relations to identity-preserving weight tokens."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,TOWER,SOURCE,TARGET,GEAR,WEIGHT,RELATION,GOAL,BAD=5,11,12,8,14,10,6,13,15
LEVELS=[
 {"name":"Gear Pair","seq":(1,)},{"name":"Changed Weights","seq":(2,1)},
 {"name":"Mapped Phase","seq":(1,3,2)},{"name":"Fault Relation","seq":(2,1,4,3)},
 {"name":"Surface Invariance","seq":(1,2,4,1,3,2)},
 {"name":"Escapement Analogy","seq":(2,1,4,2,3,1,4,2,3)}]
def advance(s,a):
 source,target,surface,fault,mapped=s
 x,y=source;u,v=target
 if a==1:x=(x+1+fault)%4;u=(u+2)%4
 elif a==2:y=(y+2+surface)%5;v=(v+1+fault)%5
 elif a==3:mapped=((y-x)%5,(v-u)%5,fault)
 elif a==4:surface=(surface+1)%3;fault=(fault+surface)%4
 elif a==5:mapped=(mapped,surface,source,target)
 return (x,y),(u,v),surface,fault,mapped
for x in LEVELS:
 s=((0,1),(2,3),0,0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=TOWER;f[8:34,7:29]=SOURCE;f[8:34,35:57]=TARGET
  for side,pair in enumerate((g.source,g.target)):
   ox=10+side*28
   for i,v in enumerate(pair):
    f[13+i*11:21+i*11,ox:ox+16]=GEAR if side==0 else WEIGHT
    f[15+i*11:19+i*11,ox+3:ox+3+v*2+3]=RELATION
  f[40:44,8:8+g.surface*15+10]=SOURCE;f[47:51,8:8+g.fault*11+7]=TARGET
  if g.mapped:f[54:58,8:56]=RELATION
  if isinstance(g.mapped,tuple) and len(g.mapped)==4:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q678(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target_state=self.cfg["target"]
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q678",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.source=(0,1);self.target=(2,3);self.surface=self.fault=0;self.mapped=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target_state=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.source,self.target,self.surface,self.fault,self.mapped=advance((self.source,self.target,self.surface,self.fault,self.mapped),a)
  elif a==6:
   if (self.source,self.target,self.surface,self.fault,self.mapped)==self.target_state:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
