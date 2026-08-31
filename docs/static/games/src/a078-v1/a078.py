"""a078 Pantograph Path -- calibrate scale and reflection before tracing remotely."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,DRAFT,LINK,PIVOT,CURSOR,TIP,TARGET,OBSTACLE,TRACE,BAD=6,8,9,14,12,10,13,4,11,15
LEVELS=[
 {"name":"Move Cursor X","seq":(1,)},{"name":"Move Cursor Y","seq":(2,)},
 {"name":"Change Pivot","seq":(3,1,2)},{"name":"Trace Remote Tip","seq":(1,2,4,3,1)},
 {"name":"Reflected Scale","seq":(3,1,1,2,4,2,4)},{"name":"Pantograph Path","seq":(1,2,3,1,4,2,3,1,2,4)},
]
def tip_for(cursor,pivot):
 x,y=cursor;scale=1+pivot%2;reflect=-1 if pivot>=2 else 1;return (32+reflect*(x-3)*scale,32+(y-3)*scale)
def advance(s,a):
 cursor,pivot,tip,path,hits,calibration,history,snapshot=s;c=list(cursor)
 if a==1:c[0]=(c[0]+1)%7;history=(history+(1,))[-8:]
 elif a==2:c[1]=(c[1]+1)%7;history=(history+(2,))[-8:]
 elif a==3:pivot=(pivot+1)%4;calibration=(calibration+1)%6;history=(history+(3,))[-8:]
 elif a==4:path=(path+(tip,))[-8:];hits=(hits+int(26<=tip[0]<=38 and 20<=tip[1]<=29))%6;history=(history+(4,))[-8:]
 if a in (1,2,3):tip=tip_for(tuple(c),pivot)
 elif a==5:snapshot=(tuple(c),pivot,tip,path,hits,calibration,history)
 return tuple(c),pivot,tip,path,hits,calibration,history,snapshot
for x in LEVELS:
 s=((3,3),0,tip_for((3,3),0),(),0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=DRAFT;cx=10+g.cursor[0]*3;cy=35+g.cursor[1]*3;tx,ty=g.tip
  tx=max(7,min(56,tx));ty=max(7,min(56,ty));px=32+(g.pivot-1)*5;py=32
  for ax,ay,bx,by in ((cx,cy,px,py),(px,py,tx,ty),(cx,cy,tx,ty)):
   for i in range(13):x=ax+(bx-ax)*i//12;y=ay+(by-ay)*i//12;f[y:y+2,x:x+2]=LINK
  f[py-3:py+4,px-3:px+4]=PIVOT;f[cy-3:cy+4,cx-3:cx+4]=CURSOR;f[ty-3:ty+4,tx-3:tx+4]=TIP
  f[20:30,26:39]=OBSTACLE;f[9:14,42:55]=TARGET
  for x,y in g.path:x=max(5,min(58,x));y=max(5,min(58,y));f[y:y+2,x:x+2]=TRACE
  if g.bad:f[1:4,18:46]=BAD
  return f
class A078(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a078",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.cursor,self.pivot,self.tip,self.path,self.hits,self.calibration,self.history,self.snapshot=((3,3),0,tip_for((3,3),0),(),0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.cursor,self.pivot,self.tip,self.path,self.hits,self.calibration,self.history,self.snapshot=advance((self.cursor,self.pivot,self.tip,self.path,self.hits,self.calibration,self.history,self.snapshot),a)
  elif a==6:
   if (self.cursor,self.pivot,self.tip,self.path,self.hits,self.calibration,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
