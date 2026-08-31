"""a056 Pull System -- trigger production from downstream demand signals."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,PLANT,PIPE,MACHINE,REQUEST,SOCKET,INVENTORY,JAM,CYCLE,SELECT=0,8,9,12,14,10,11,15,6,13
LEVELS=[
 {"name":"Read Demand","seq":(3,)},{"name":"Consume Then Pull","seq":(1,3)},
 {"name":"Select Machine","seq":(2,3,1)},{"name":"Circulate Stock","seq":(3,2,3,4,1)},
 {"name":"Avoid Overproduction","seq":(1,3,2,3,4,2,1)},{"name":"Pull System","seq":(3,1,2,3,4,1,2,3,4,1)},
]
def advance(s,a):
 requests,inventory,cursor,jam,cycles,history,snapshot=s;r=list(requests);inv=list(inventory)
 if a==1:
  if inv[cursor]:inv[cursor]-=1
  else:r[cursor]=1
  cursor=(cursor+1)%3;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%3;history=(history+(2,))[-8:]
 elif a==3:
  if r[cursor] and inv[cursor]<2:inv[cursor]+=1;r[cursor]=0;cycles=(cycles+1)%7
  else:jam=(jam+1)%6
  history=(history+(3,))[-8:]
 elif a==4:
  nxt=(cursor+1)%3
  if inv[cursor] and inv[nxt]<2:inv[cursor]-=1;inv[nxt]+=1
  if r[nxt] and inv[nxt]:inv[nxt]-=1;r[nxt]=0
  history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(r),tuple(inv),cursor,jam,cycles,history)
 return tuple(r),tuple(inv),cursor,jam,cycles,history,snapshot
for x in LEVELS:
 s=((1,0,1),(0,0,0),0,0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=PLANT
  for i in range(3):
   x=8+i*18;f[12:28,x:x+13]=MACHINE;f[31:36,x+4:x+9]=PIPE;f[39:52,x:x+13]=SOCKET
   if g.requests[i]:f[42:49,x+3:x+10]=REQUEST
   for j in range(g.inventory[i]):f[30-j*5:34-j*5,x+5:x+9]=INVENTORY
   if i==g.cursor:f[7:11,x:x+13]=SELECT
  for i in range(g.cycles):f[55:58,8+i*6:13+i*6]=CYCLE
  for i in range(g.jam):f[5:8,41+i*3:44+i*3]=JAM
  return f
class A056(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a056",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.requests,self.inventory,self.cursor,self.jam,self.cycles,self.history,self.snapshot=((1,0,1),(0,0,0),0,0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.requests,self.inventory,self.cursor,self.jam,self.cycles,self.history,self.snapshot=advance((self.requests,self.inventory,self.cursor,self.jam,self.cycles,self.history,self.snapshot),a)
  elif a==6:
   if (self.requests,self.inventory,self.cursor,self.jam,self.cycles,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
