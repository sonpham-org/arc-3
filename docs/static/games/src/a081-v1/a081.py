"""a081 Keystone -- close an arch, then remove temporary supports in order."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,SITE,STONE,KEYSTONE,SUPPORT,LOAD,FORCE,STABLE,CRACK,BAD=9,8,4,12,14,10,11,13,6,15
LEVELS=[
 {"name":"Place Support","seq":(1,)},{"name":"Set Keystone","seq":(1,2)},
 {"name":"Remove Support","seq":(1,2,3)},{"name":"Test Load","seq":(1,1,2,3,4)},
 {"name":"Removal Order","seq":(1,1,2,3,3,4,4)},{"name":"Keystone","seq":(1,2,1,3,4,1,3,4,4,3)},
]
def advance(s,a):
 supports,keystone,load,force,cracks,history,snapshot=s;sp=list(supports)
 if a==1:
  i=0 if not sp[0] else 1;sp[i]=1;history=(history+(1,))[-8:]
 elif a==2:keystone^=1;force=(force+2*keystone)%7;history=(history+(2,))[-8:]
 elif a==3:
  i=1 if sp[1] else 0
  if sp[i]:sp[i]=0
  if not keystone and not any(sp):cracks=(cracks+1)%6
  history=(history+(3,))[-8:]
 elif a==4:load=(load+1)%7;force=(force+1+keystone)%7;cracks=(cracks+int(not keystone and not any(sp)))%6;history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(sp),keystone,load,force,cracks,history)
 return tuple(sp),keystone,load,force,cracks,history,snapshot
for x in LEVELS:
 s=((0,0),0,0,0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=SITE
  blocks=((8,42),(12,33),(18,25),(26,19),(38,25),(44,33),(48,42))
  for i,(x,y) in enumerate(blocks):f[y:y+10,x:x+9]=KEYSTONE if i==3 and g.keystone else STONE
  for i,on in enumerate(g.supports):
   if on:x=21+i*18;f[31:54,x:x+6]=SUPPORT
  f[7:11,8:18]=KEYSTONE;f[7:11,20:30]=SUPPORT;f[7:11,32:42]=STABLE
  x=9+g.load*7;f[12:19,x:x+7]=LOAD
  f[54:58,8:8+g.force*6]=FORCE
  for i in range(g.cracks):f[8+i*3:10+i*3,49:57]=CRACK
  if g.keystone and not any(g.supports):f[49:53,25:39]=STABLE
  if g.bad:f[1:4,18:46]=BAD
  return f
class A081(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a081",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.supports,self.keystone,self.load,self.force,self.cracks,self.history,self.snapshot=((0,0),0,0,0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.supports,self.keystone,self.load,self.force,self.cracks,self.history,self.snapshot=advance((self.supports,self.keystone,self.load,self.force,self.cracks,self.history,self.snapshot),a)
  elif a==6:
   if (self.supports,self.keystone,self.load,self.force,self.cracks,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
