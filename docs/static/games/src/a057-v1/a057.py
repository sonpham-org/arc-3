"""a057 Thermostat Tiles -- regulate a delayed temperature field inside a band."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,ROOM,TILE,COLD,WARM,HOT,HEATER,BAND,LAG,BAD=1,8,9,6,12,14,10,13,11,15
LEVELS=[
 {"name":"Toggle Heater","seq":(1,)},{"name":"Observe Lag","seq":(1,3)},
 {"name":"Select Sensor","seq":(2,1,3)},{"name":"Hold The Band","seq":(1,3,2,1,3)},
 {"name":"Shift Setpoint","seq":(4,1,3,2,1,3,3)},{"name":"Thermostat Tiles","seq":(1,3,2,1,3,4,2,1,3,3)},
]
def advance(s,a):
 temps,heaters,lag,cursor,band,stable,history,snapshot=s;t=list(temps);h=list(heaters);lg=list(lag)
 if a==1:h[cursor]^=1;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%4;history=(history+(2,))[-8:]
 elif a==3:
  for i in range(4):t[i]=max(0,min(6,t[i]+lg[i]))
  lg=[(1 if h[i] else -1 if t[i]>band else 0)+(1 if h[(i-1)%4] and not h[i] else 0) for i in range(4)]
  stable=min(5,stable+1) if all(abs(v-band)<=1 for v in t) else 0;history=(history+(3,))[-8:]
 elif a==4:band=2+(band-1)%4;stable=0;history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(t),tuple(h),tuple(lg),cursor,band,stable,history)
 return tuple(t),tuple(h),tuple(lg),cursor,band,stable,history,snapshot
for x in LEVELS:
 s=((1,2,4,5),(0,0,0,0),(0,0,0,0),0,3,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=ROOM
  colors=(COLD,COLD,WARM,WARM,HOT,HOT,HOT)
  for i,v in enumerate(g.temps):
   x=8+i*13;f[20:40,x:x+11]=TILE;f[35-v*2:39,x+2:x+9]=colors[v]
   f[43:50,x+2:x+9]=HEATER if g.heaters[i] else TILE
   if i==g.cursor:f[14:18,x:x+11]=LAG
  f[8:12,9:9+g.band*8]=BAND
  for i in range(g.stable):f[54:58,9+i*9:16+i*9]=BAND
  if g.bad:f[1:4,18:46]=BAD
  return f
class A057(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a057",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.temps,self.heaters,self.lag,self.cursor,self.band,self.stable,self.history,self.snapshot=((1,2,4,5),(0,0,0,0),(0,0,0,0),0,3,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.temps,self.heaters,self.lag,self.cursor,self.band,self.stable,self.history,self.snapshot=advance((self.temps,self.heaters,self.lag,self.cursor,self.band,self.stable,self.history,self.snapshot),a)
  elif a==6:
   if (self.temps,self.heaters,self.lag,self.cursor,self.band,self.stable,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
