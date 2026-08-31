"""a146 Hidden Puppeteer -- distinguish a common controller from local coordination."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,STAGE,CREATURE_A,CREATURE_B,BLOCK,CONTROL,PULSE,CURSOR,COMMON,LOCAL=13,8,12,14,6,10,11,9,4,7
BAD=15
LEVELS=[
 {"name":"Block Creature","seq":(1,)},{"name":"Select Creature","seq":(2,)},
 {"name":"Send Pulse","seq":(3,1)},{"name":"Compare Responses","seq":(1,2,3,4,2)},
 {"name":"Find Controller","seq":(1,3,2,1,4,3,2)},{"name":"Hidden Puppeteer","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 blocked,cursor,pulse,positions,common,local,history,snapshot=s;p=list(positions)
 if a==1:blocked^=1<<cursor;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%6;history=(history+(2,))[-8:]
 elif a==3:
  pulse=(pulse+1)%4
  for i in range(6):
   if not ((blocked>>i)&1):p[i]=(p[i]+(1 if i<3 else (i+pulse)%2))%7
  history=(history+(3,))[-8:]
 elif a==4:common=sum(int(not ((blocked>>i)&1)) for i in range(3));local=sum(int(p[i]%2==(i+pulse)%2) for i in range(3,6));history=(history+(4,))[-8:]
 elif a==5:snapshot=(blocked,cursor,pulse,tuple(p),common,local,history)
 return blocked,cursor,pulse,tuple(p),common,local,history,snapshot
for q in LEVELS:
 s=(0,0,0,(0,1,2,4,5,6),3,1,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=STAGE
  for i,p in enumerate(g.positions):
   x=9+p*7;y=14+(i%3)*14;f[y:y+10,x:x+9]=CREATURE_A if i<3 else CREATURE_B
   if (g.blocked>>i)&1:f[y+3:y+7,x-2:x+11]=BLOCK
   if i==g.cursor:f[y-3:y,x:x+9]=CURSOR
  f[7:10,8:8+g.pulse*9]=PULSE;f[54:58,8:8+g.common*11]=COMMON;f[54:58,43:43+g.local*4]=LOCAL
  if g.bad:f[1:4,18:46]=BAD
  return f
class A146(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a146",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.blocked,self.cursor,self.pulse,self.positions,self.common,self.local,self.history,self.snapshot=(0,0,0,(0,1,2,4,5,6),3,1,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.blocked,self.cursor,self.pulse,self.positions,self.common,self.local,self.history,self.snapshot=advance((self.blocked,self.cursor,self.pulse,self.positions,self.common,self.local,self.history,self.snapshot),a)
  elif a==6:
   if (self.blocked,self.cursor,self.pulse,self.positions,self.common,self.local,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
