"""a091 Pinched Tube -- shape a deformable conduit around one fluid pulse."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,LAB,TUBE,FLUID,CLAMP,BULGE,RECEIVER,PRESSURE,FLOW,BAD=3,8,9,12,14,10,13,11,6,15
LEVELS=[
 {"name":"Place Clamp","seq":(1,)},{"name":"Select Segment","seq":(2,)},
 {"name":"Send Pulse","seq":(1,3)},{"name":"Pressure Bulge","seq":(1,2,1,3,4)},
 {"name":"Split Receivers","seq":(2,1,3,2,1,4,3)},{"name":"Pinched Tube","seq":(1,2,1,3,4,2,1,3,4,3)},
]
def advance(s,a):
 widths,clamps,cursor,pulse,receivers,pressure,history,snapshot=s;w=list(widths);c=list(clamps);r=list(receivers)
 if a==1:c[cursor]^=1;w[cursor]=max(1,w[cursor]-2) if c[cursor] else min(5,w[cursor]+2);history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%5;history=(history+(2,))[-8:]
 elif a==3:
  pulse=(pulse+1)%6;pressure=(pressure+sum(5-x for x in w))%8;r[0]=(r[0]+w[0]+w[2])%7;r[1]=(r[1]+w[1]+w[4])%7
  for i in range(5):
   if not c[i] and pressure>4:w[i]=min(7,w[i]+1)
  history=(history+(3,))[-8:]
 elif a==4:
  pressure=max(0,pressure-2);w=[max(2,x-1) if not c[i] else x for i,x in enumerate(w)];history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(w),tuple(c),cursor,pulse,tuple(r),pressure,history)
 return tuple(w),tuple(c),cursor,pulse,tuple(r),pressure,history,snapshot
for x in LEVELS:
 s=((4,4,4,4,4),(0,0,0,0,0),0,0,(0,0),0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=LAB
  for i,w in enumerate(g.widths):x=7+i*9;y=31-w;f[y:34+w,x:x+9]=BULGE if w>4 else TUBE;f[29:36,x+2:x+7]=FLUID
  for i,on in enumerate(g.clamps):
   if on:x=9+i*9;f[20:45,x:x+4]=CLAMP
  f[15:19,7+g.cursor*9:15+g.cursor*9]=FLOW
  for i,v in enumerate(g.receivers):x=17+i*28;f[48:57,x:x+14]=RECEIVER;f[54-v:56,x+2:x+12]=FLUID
  f[8:12,8:8+g.pressure*6]=PRESSURE
  if g.bad:f[1:4,18:46]=BAD
  return f
class A091(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a091",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.widths,self.clamps,self.cursor,self.pulse,self.receivers,self.pressure,self.history,self.snapshot=((4,4,4,4,4),(0,0,0,0,0),0,0,(0,0),0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.widths,self.clamps,self.cursor,self.pulse,self.receivers,self.pressure,self.history,self.snapshot=advance((self.widths,self.clamps,self.cursor,self.pulse,self.receivers,self.pressure,self.history,self.snapshot),a)
  elif a==6:
   if (self.widths,self.clamps,self.cursor,self.pulse,self.receivers,self.pressure,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
