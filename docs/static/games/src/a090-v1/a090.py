"""a090 Soft Key -- compress through a lock, then expand into required pins."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,LOCK,CHANNEL,KEY,PIN,COMPRESS,EXPAND,CONTACT,CAVITY,BAD=2,8,9,12,14,10,13,6,11,15
LEVELS=[
 {"name":"Compress Width","seq":(1,)},{"name":"Compress Height","seq":(2,)},
 {"name":"Enter Lock","seq":(1,3)},{"name":"Expand In Cavity","seq":(1,3,4)},
 {"name":"Contact Pins","seq":(2,3,1,3,4,3,4)},{"name":"Soft Key","seq":(1,3,2,3,4,1,3,4,2,4)},
]
def advance(s,a):
 shape,pos,compressed,contacts,cavity,history,snapshot=s;w,h=shape
 if a==1:w=max(2,w-2);h=min(8,h+1);compressed=1;history=(history+(1,))[-8:]
 elif a==2:h=max(2,h-2);w=min(10,w+1);compressed=2;history=(history+(2,))[-8:]
 elif a==3:pos=min(9,pos+1+int(w<=5));cavity=(cavity+int(pos in (4,7)))%5;history=(history+(3,))[-8:]
 elif a==4:w=min(9,w+2);h=min(8,h+2);compressed=0;contacts=(contacts+sum(int(pos+d in (4,7,9)) for d in (-1,0,1)))%7;history=(history+(4,))[-8:]
 elif a==5:snapshot=((w,h),pos,compressed,contacts,cavity,history)
 return (w,h),pos,compressed,contacts,cavity,history,snapshot
for x in LEVELS:
 s=((8,5),0,0,0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=LOCK;f[24:41,6:58]=CHANNEL
  for x in (27,42,53):f[17:24,x:x+4]=PIN;f[41:48,x:x+4]=PIN
  f[13:52,30:36]=CAVITY;f[13:52,45:51]=CAVITY
  x=7+g.pos*5;w,h=g.shape;y=32-h//2;f[y:y+h,x:x+w]=KEY
  f[8:12,8:8+(9-w)*5]=COMPRESS;f[53:57,8:8+g.contacts*6]=CONTACT
  if not g.compressed:f[8:12,43:57]=EXPAND
  if g.bad:f[1:4,18:46]=BAD
  return f
class A090(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a090",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.shape,self.pos,self.compressed,self.contacts,self.cavity,self.history,self.snapshot=((8,5),0,0,0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.shape,self.pos,self.compressed,self.contacts,self.cavity,self.history,self.snapshot=advance((self.shape,self.pos,self.compressed,self.contacts,self.cavity,self.history,self.snapshot),a)
  elif a==6:
   if (self.shape,self.pos,self.compressed,self.contacts,self.cavity,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
