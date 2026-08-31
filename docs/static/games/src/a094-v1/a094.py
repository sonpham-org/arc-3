"""a094 Elastic Net -- move local nodes under distributed tension limits."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,ARENA,STRAND,NODE,SELECT,POCKET,OBJECT,TENSION,LIMIT,BAD=6,8,9,12,14,10,13,11,4,15
LEVELS=[
 {"name":"Drag Node","seq":(1,)},{"name":"Select Node","seq":(3,)},
 {"name":"Relax Node","seq":(2,1)},{"name":"Catch Object","seq":(1,3,1,4,2)},
 {"name":"Distributed Tension","seq":(1,3,1,4,2,3,2)},{"name":"Elastic Net","seq":(1,3,1,4,2,3,1,4,2,1)},
]
def advance(s,a):
 offsets,cursor,tension,pockets,caught,history,snapshot=s;o=list(offsets)
 if a==1:
  o[cursor]=min(5,o[cursor]+1)
  for i in range(6):
   if i!=cursor:o[i]+=(o[cursor]-o[i])//3
  history=(history+(1,))[-8:]
 elif a==2:o[cursor]=max(-3,o[cursor]-1);history=(history+(2,))[-8:]
 elif a==3:cursor=(cursor+1)%6;history=(history+(3,))[-8:]
 elif a==4:pockets=(pockets+1)%5;caught=(caught+int(sum(abs(x) for x in o)<12))%6;history=(history+(4,))[-8:]
 if a in (1,2,3,4):tension=sum(abs(o[i]-o[(i+1)%6]) for i in range(6))
 elif a==5:snapshot=(tuple(o),cursor,tension,pockets,caught,history)
 return tuple(o),cursor,tension,pockets,caught,history,snapshot
for x in LEVELS:
 s=((0,0,0,0,0,0),0,0,0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=ARENA;base=((13,17),(31,12),(49,17),(49,43),(31,50),(13,43));pts=[]
  for i,(x,y) in enumerate(base):y+=g.offsets[i]*2;pts.append((x,y));f[y-3:y+4,x-3:x+4]=SELECT if i==g.cursor else NODE
  for i in range(6):
   x1,y1=pts[i];x2,y2=pts[(i+1)%6]
   for j in range(13):x=x1+(x2-x1)*j//12;y=y1+(y2-y1)*j//12;f[y:y+2,x:x+2]=STRAND
  f[26:39,25:39]=POCKET;f[7:12,28:36]=OBJECT;f[54:58,8:8+min(8,g.tension)*6]=TENSION;f[8:11,43:57]=LIMIT
  if g.bad:f[1:4,18:46]=BAD
  return f
class A094(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a094",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.offsets,self.cursor,self.tension,self.pockets,self.caught,self.history,self.snapshot=((0,0,0,0,0,0),0,0,0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.offsets,self.cursor,self.tension,self.pockets,self.caught,self.history,self.snapshot=advance((self.offsets,self.cursor,self.tension,self.pockets,self.caught,self.history,self.snapshot),a)
  elif a==6:
   if (self.offsets,self.cursor,self.tension,self.pockets,self.caught,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
