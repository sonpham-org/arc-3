"""q517 Catalyst Frame -- store an orientation, move the pipe frame, then execute it hidden."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,REFINERY,PIPE,BEAD,FRAME,MEMORY,HIDDEN,PRODUCT,BAD=0,12,9,14,10,6,13,11,15
LEVELS=[
 {"name":"First Memory","seq":(1,3,4)},{"name":"Rotated Pipe","seq":(2,1,3,4)},
 {"name":"Stored Frame","seq":(1,3,2,4)},{"name":"Moving Refinery","seq":(2,1,3,2,1,4)},
 {"name":"Double Rotation","seq":(1,2,1,3,2,2,4)},{"name":"Catalyst Frame","seq":(2,1,2,1,3,2,1,4)}]
def advance(s,a,x):
 local,frame,visible,memory,product=s
 if a==1:local=(local+(1,2,-1,-2)[frame])%4
 elif a==2:frame=(frame+1)%4
 elif a==3:memory=(local+frame)%4;visible=1
 elif a==4:
  if memory is None:return None
  visible=0;product=(memory-frame)%4
 elif a==5:
  if (local,frame,visible,memory,product)!=x["goal"]:return None
 return local,frame,visible,memory,product
for x in LEVELS:
 s=(0,0,1,None,None)
 for a in x["seq"]:s=advance(s,a,x);assert s is not None
 x["goal"]=s;x["plan"]=x["seq"]+(5,)
def target(x):
 s=(0,0,1,None,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=REFINERY
  for i in range(4):f[8+i*7:13+i*7,8:56]=PIPE+i%2
  f[10+g.local*7:14+g.local*7,12:20]=BEAD;f[39:43,8:8+g.frame*12]=FRAME;f[47:51,8:28]=MEMORY
  if g.memory is not None:f[47:52,36:36+g.memory*5+5]=MEMORY
  if not g.visible:f[54:58,8:28]=HIDDEN
  if g.product is not None:f[54:59,39:56]=PRODUCT+g.product
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q517(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q517",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.local=self.frame=0;self.visible=1;self.memory=self.product=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.local,self.frame,self.visible,self.memory,self.product),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.local,self.frame,self.visible,self.memory,self.product=s
  elif a==6:
   if (self.local,self.frame,self.visible,self.memory,self.product)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
