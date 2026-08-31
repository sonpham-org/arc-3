"""a104 Pulse Packet -- precompensate component spacing for dispersion."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,CHANNEL,COMP_A,COMP_B,COMP_C,RECEIVER,PACKET,SPACING,TIME,BAD=0,8,12,14,10,13,11,9,6,15
LEVELS=[
 {"name":"Shift Component","seq":(1,)},{"name":"Select Color","seq":(2,)},
 {"name":"Advance Packet","seq":(1,3)},{"name":"Moving Receiver","seq":(1,2,1,3,4)},
 {"name":"Precompensate","seq":(2,1,3,2,1,4,3)},{"name":"Pulse Packet","seq":(1,2,1,3,4,2,1,3,4,3)},
]
def advance(s,a):
 positions,cursor,time,receiver,cohesion,history,snapshot=s;p=list(positions)
 if a==1:p[cursor]=(p[cursor]+1)%12;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%3;history=(history+(2,))[-8:]
 elif a==3:
  for i,v in enumerate((1,2,3)):p[i]=(p[i]+v)%12
  time=(time+1)%12;receiver=(receiver+2)%12;cohesion=12-(max(p)-min(p));history=(history+(3,))[-8:]
 elif a==4:receiver=(receiver+1)%12;cohesion=(cohesion+int(all(abs(x-receiver)<=2 for x in p)))%13;history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(p),cursor,time,receiver,cohesion,history)
 return tuple(p),cursor,time,receiver,cohesion,history,snapshot
for x in LEVELS:
 s=((0,3,6),0,0,10,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=CHANNEL;cols=(COMP_A,COMP_B,COMP_C)
  for i,p in enumerate(g.positions):x=7+p*4;y=17+i*12;f[y:y+8,x:x+7]=cols[i];f[12+i*12:15+i*12,7:57]=SPACING
  x=7+g.receiver*4;f[10:53,x:x+5]=RECEIVER
  f[53:57,8:8+min(12,g.cohesion)*4]=PACKET;f[7:11,8:8+g.time*4]=TIME
  f[56:59,47:57]=cols[g.cursor]
  if g.bad:f[1:4,18:46]=BAD
  return f
class A104(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a104",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.positions,self.cursor,self.time,self.receiver,self.cohesion,self.history,self.snapshot=((0,3,6),0,0,10,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.positions,self.cursor,self.time,self.receiver,self.cohesion,self.history,self.snapshot=advance((self.positions,self.cursor,self.time,self.receiver,self.cohesion,self.history,self.snapshot),a)
  elif a==6:
   if (self.positions,self.cursor,self.time,self.receiver,self.cohesion,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
