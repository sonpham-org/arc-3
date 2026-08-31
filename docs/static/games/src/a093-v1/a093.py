"""a093 Viscous Block -- alternate impulses and holds in a rate-dependent blob."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,COURSE,FLOOR,BLOB,CARGO,IMPULSE,FLOW,GAP,WAIT,BAD=5,8,9,12,14,10,13,4,6,15
LEVELS=[
 {"name":"Quick Push","seq":(1,)},{"name":"Sustained Hold","seq":(2,)},
 {"name":"Wait For Flow","seq":(2,3)},{"name":"Cross Gap","seq":(1,2,3,4,1)},
 {"name":"Retain Cargo","seq":(2,3,1,4,2,3,4)},{"name":"Viscous Block","seq":(1,2,3,4,2,3,1,4,3,1)},
]
def advance(s,a):
 pos,width,height,pressure,wait,cargo,history,snapshot=s
 if a==1:pos=min(10,pos+1);pressure=min(5,pressure+2);width=max(3,width-1);height=min(8,height+1);history=(history+(1,))[-8:]
 elif a==2:pressure=min(6,pressure+1);wait+=1;width=min(10,width+2);height=max(2,height-1);history=(history+(2,))[-8:]
 elif a==3:
  if pressure:pos=min(10,pos+pressure//2);width=min(11,width+1);height=max(2,height-1)
  pressure=max(0,pressure-1);wait+=1;history=(history+(3,))[-8:]
 elif a==4:cargo=(cargo+int(width<=7 and height>=3))%6;pressure=0;history=(history+(4,))[-8:]
 elif a==5:snapshot=(pos,width,height,pressure,wait,cargo,history)
 return pos,width,height,pressure,wait,cargo,history,snapshot
for x in LEVELS:
 s=(0,7,5,0,0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=COURSE;f[43:52,6:26]=FLOOR;f[43:52,39:58]=FLOOR;f[43:52,26:39]=GAP
  x=8+g.pos*4;y=43-g.height;f[y:43,x:x+g.width]=BLOB;f[y-7:y,x+2:x+8]=CARGO
  f[8:12,8:8+g.pressure*7]=IMPULSE;f[14:18,8:8+min(7,g.wait)*6]=WAIT
  for i in range(g.cargo):f[54:58,8+i*7:14+i*7]=FLOW
  if g.bad:f[1:4,18:46]=BAD
  return f
class A093(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a093",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.pos,self.width,self.height,self.pressure,self.wait,self.cargo,self.history,self.snapshot=(0,7,5,0,0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.pos,self.width,self.height,self.pressure,self.wait,self.cargo,self.history,self.snapshot=advance((self.pos,self.width,self.height,self.pressure,self.wait,self.cargo,self.history,self.snapshot),a)
  elif a==6:
   if (self.pos,self.width,self.height,self.pressure,self.wait,self.cargo,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
