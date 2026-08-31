"""a189 Noisy Handshake -- retry a request while suppressing duplicate completion."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,NETWORK,SENDER,RECEIVER,REQUEST,ACK,NOISE,RETRY,DONE,DUPLICATE,CURSOR=11,1,12,14,10,4,6,9,5,8,13
BAD=15
LEVELS=[
 {"name":"Send Request","seq":(1,)},{"name":"Cross Noise","seq":(2,)},
 {"name":"Retry Once","seq":(3,1)},{"name":"Confirm Ack","seq":(1,2,3,4,2)},
 {"name":"Suppress Duplicate","seq":(1,3,2,1,4,3,2)},{"name":"Noisy Handshake","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 requested,acked,retries,cycle,completed,duplicates,history,snapshot=s
 if a==1:
  if requested:duplicates+=1
  requested=True;history=(history+(1,))[-8:]
 elif a==2:acked=requested and cycle%3!=1;history=(history+(2,))[-8:]
 elif a==3:retries+=int(requested and not acked);cycle=(cycle+1)%6;history=(history+(3,))[-8:]
 elif a==4:completed=int(requested and acked);duplicates=max(0,duplicates-completed);history=(history+(4,))[-8:]
 elif a==5:snapshot=(requested,acked,retries,cycle,completed,duplicates,history)
 return requested,acked,retries,cycle,completed,duplicates,history,snapshot
for q in LEVELS:
 s=(False,False,0,0,0,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=NETWORK;f[22:43,7:18]=SENDER;f[22:43,46:57]=RECEIVER
  f[27:32,18:46]=REQUEST if g.requested else NOISE;f[35:40,18:46]=ACK if g.acked else RETRY
  for i in range(6):f[10:15,8+i*8:14+i*8]=CURSOR if i==g.cycle else NOISE
  f[50:56,8:8+g.completed*24]=DONE;f[50:56,35:35+min(4,g.duplicates)*5]=DUPLICATE;f[16:19,8:8+min(6,g.retries)*7]=RETRY
  if g.bad:f[1:4,18:46]=BAD
  return f
class A189(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a189",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.requested,self.acked,self.retries,self.cycle,self.completed,self.duplicates,self.history,self.snapshot=(False,False,0,0,0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.requested,self.acked,self.retries,self.cycle,self.completed,self.duplicates,self.history,self.snapshot=advance((self.requested,self.acked,self.retries,self.cycle,self.completed,self.duplicates,self.history,self.snapshot),a)
  elif a==6:
   if (self.requested,self.acked,self.retries,self.cycle,self.completed,self.duplicates,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
