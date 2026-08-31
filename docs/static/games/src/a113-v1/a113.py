"""a113 Stable Pairing -- remove every mutually preferred blocking pair."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,HALL,LEFT,RIGHT,PAIR,PREFERENCE,BLOCKING,STABLE,CURSOR,BAD=10,8,12,14,9,11,6,4,13,15
LEVELS=[
 {"name":"Change Partner","seq":(1,)},{"name":"Select Agent","seq":(2,)},
 {"name":"Reveal Preference","seq":(3,1)},{"name":"Find Blocker","seq":(1,2,3,4,2)},
 {"name":"Repair Matching","seq":(1,3,2,1,4,3,2)},{"name":"Stable Pairing","seq":(1,2,3,1,4,2,1,3,4,2)},
]
def advance(s,a):
 partners,cursor,round_,blocking,mutual,history,snapshot=s;p=list(partners)
 if a==1:p[cursor]=(p[cursor]+1)%4;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%4;history=(history+(2,))[-8:]
 elif a==3:round_=(round_+1)%4;history=(history+(3,))[-8:]
 elif a==4:
  blocking=0;mutual=0
  for i,assigned in enumerate(p):
   preferred=(i+round_+1)%4;wants=assigned!=preferred;reciprocal=p[(preferred-round_)%4]!=i;blocking+=int(wants and reciprocal);mutual+=int(not wants)
  history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(p),cursor,round_,blocking,mutual,history)
 return tuple(p),cursor,round_,blocking,mutual,history,snapshot
for x in LEVELS:
 s=((0,1,2,3),0,0,0,4,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=HALL
  for i,p in enumerate(g.partners):
   y=12+i*11;f[y:y+7,8:15]=LEFT;f[12+p*11:19+p*11,49:56]=RIGHT
   yy=15+p*11;f[min(y+3,yy):max(y+4,yy+1),15:49]=PAIR
   if i==g.cursor:f[y-3:y,7:16]=CURSOR
  for i in range(g.round+1):f[7:10,20+i*7:25+i*7]=PREFERENCE
  f[54:58,8:8+g.blocking*9]=BLOCKING;f[54:58,45:45+g.mutual*3]=STABLE
  if g.bad:f[1:4,18:46]=BAD
  return f
class A113(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a113",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.partners,self.cursor,self.round,self.blocking,self.mutual,self.history,self.snapshot=((0,1,2,3),0,0,0,4,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.partners,self.cursor,self.round,self.blocking,self.mutual,self.history,self.snapshot=advance((self.partners,self.cursor,self.round,self.blocking,self.mutual,self.history,self.snapshot),a)
  elif a==6:
   if (self.partners,self.cursor,self.round,self.blocking,self.mutual,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
