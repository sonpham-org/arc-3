"""a062 Hysteresis House -- exploit different door-open and door-close thresholds."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,HOUSE,ROOM,COLD,HOT,DOOR,OPEN,PERSON,THERMO,BAD=6,8,9,10,12,14,13,11,4,15
LEVELS=[
 {"name":"Heat Room","seq":(1,)},{"name":"Open Threshold","seq":(1,1)},
 {"name":"Memory Band","seq":(1,1,2)},{"name":"Traverse Door","seq":(1,1,2,4)},
 {"name":"Door Sequence","seq":(1,1,3,1,2,4,4)},{"name":"Hysteresis House","seq":(1,1,2,3,1,4,2,4,3,4)},
]
def update_doors(temps,doors):
 d=list(doors)
 for i,t in enumerate(temps):
  if not d[i] and t>=5:d[i]=1
  elif d[i] and t<=2:d[i]=0
 return tuple(d)
def advance(s,a):
 temps,doors,cursor,person,heater,history,snapshot=s;t=list(temps)
 if a==1:t[cursor]=min(7,t[cursor]+2);heater=cursor;history=(history+(1,))[-8:]
 elif a==2:t[cursor]=max(0,t[cursor]-2);heater=-1;history=(history+(2,))[-8:]
 elif a==3:cursor=(cursor+1)%3;history=(history+(3,))[-8:]
 elif a==4:
  if person<3 and doors[min(2,person)]:person+=1
  history=(history+(4,))[-8:]
 if a in (1,2):doors=update_doors(tuple(t),doors)
 elif a==5:snapshot=(tuple(t),doors,cursor,person,heater,history)
 return tuple(t),doors,cursor,person,heater,history,snapshot
for x in LEVELS:
 s=((3,4,2),(0,0,0),0,0,-1,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=HOUSE
  for i,t in enumerate(g.temps):
   x=7+i*18;f[15:49,x:x+16]=ROOM;f[43-t*4:47,x+3:x+8]=HOT if t>=4 else COLD
   f[18:43,x+13:x+16]=OPEN if g.doors[i] else DOOR
   if i==g.cursor:f[9:13,x:x+16]=THERMO
  px=9+g.person*16;f[50:57,px:px+6]=PERSON
  if g.heater>=0:x=10+g.heater*18;f[53:57,x:x+9]=HOT
  if g.bad:f[1:4,18:46]=BAD
  return f
class A062(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a062",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.temps,self.doors,self.cursor,self.person,self.heater,self.history,self.snapshot=((3,4,2),(0,0,0),0,0,-1,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.temps,self.doors,self.cursor,self.person,self.heater,self.history,self.snapshot=advance((self.temps,self.doors,self.cursor,self.person,self.heater,self.history,self.snapshot),a)
  elif a==6:
   if (self.temps,self.doors,self.cursor,self.person,self.heater,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
