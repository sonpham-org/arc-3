"""a083 Cantilever Cargo -- balance torque while shuttling loads over a void."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,VOID,DECK,SUPPORT,CARGO_A,CARGO_B,COUNTER,TORQUE,TILT,BAD=11,8,9,4,12,14,10,13,6,15
LEVELS=[
 {"name":"Move Cargo","seq":(1,)},{"name":"Move Counterweight","seq":(2,)},
 {"name":"Select Load","seq":(3,1,2)},{"name":"Balance Moment","seq":(1,2,1,4,2)},
 {"name":"Scarce Deck","seq":(3,1,2,4,1,2,4)},{"name":"Cantilever Cargo","seq":(1,3,1,2,4,2,1,3,4,1)},
]
def torque_for(pos,counter):return sum((i+1)*(p-3) for i,p in enumerate(pos))-2*(counter-2)
def advance(s,a):
 positions,counter,cursor,delivered,torque,history,snapshot=s;p=list(positions)
 if a==1:p[cursor]=min(7,p[cursor]+1);history=(history+(1,))[-8:]
 elif a==2:counter=(counter+1)%6;history=(history+(2,))[-8:]
 elif a==3:cursor^=1;history=(history+(3,))[-8:]
 elif a==4:delivered=(delivered+int(p[cursor]>=6 and abs(torque)<=5))%5;history=(history+(4,))[-8:]
 if a in (1,2,3,4):torque=torque_for(tuple(p),counter)
 elif a==5:snapshot=(tuple(p),counter,cursor,delivered,torque,history)
 return tuple(p),counter,cursor,delivered,torque,history,snapshot
for x in LEVELS:
 s=((1,2),1,0,0,torque_for((1,2),1),(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g

 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=VOID;f[28:40,6:59]=DECK;f[40:57,20:28]=SUPPORT
  for i,p in enumerate(g.positions):x=7+p*6;f[18:28,x:x+7]=CARGO_A if i==0 else CARGO_B
  x=7+g.counter*6;f[40:48,x:x+8]=COUNTER
  center=32+max(-15,min(15,g.torque));f[10:15,32:center:1 if center>=32 else -1]=TORQUE
  f[15:18,29:36]=TILT
  for i in range(g.delivered):f[52:56,44+i*3:47+i*3]=TORQUE
  if g.bad:f[1:4,18:46]=BAD
  return f
class A083(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a083",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.positions,self.counter,self.cursor,self.delivered,self.torque,self.history,self.snapshot=((1,2),1,0,0,torque_for((1,2),1),(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.positions,self.counter,self.cursor,self.delivered,self.torque,self.history,self.snapshot=advance((self.positions,self.counter,self.cursor,self.delivered,self.torque,self.history,self.snapshot),a)
  elif a==6:
   if (self.positions,self.counter,self.cursor,self.delivered,self.torque,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
